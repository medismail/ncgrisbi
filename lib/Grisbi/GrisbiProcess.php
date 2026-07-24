<?php
declare(strict_types=1);

namespace OCA\NCGrisbi\Grisbi;

use OCA\NCGrisbi\Exception\GrisbiProtocolException;

final class GrisbiProcess {
    private string $pythonBinary;
    private string $protocolScriptPath;
    private ?string $password = null;
    private int $processTimeoutSeconds = 120;

    public function __construct() {
        $this->pythonBinary = 'python3';
        $this->protocolScriptPath = __DIR__ . '/../bin/ncgrisbi_protocol.py';
    }

    /**
     * Keep the historical factory signature for test compatibility. The legacy
     * wrapper argument is intentionally ignored: every command now uses the
     * framed worker and descriptor 3 for passwords.
     */
    public static function createForTesting(
        string $pythonBinary,
        string $legacyWrapperPath,
        string $protocolScriptPath,
        int $processTimeoutSeconds = 10
    ): self {
        unset($legacyWrapperPath);
        $instance = new self();
        $instance->pythonBinary = $pythonBinary;
        $instance->protocolScriptPath = $protocolScriptPath;
        $instance->processTimeoutSeconds = $processTimeoutSeconds;
        return $instance;
    }

    public function setPassword(string $password): void {
        $this->password = $password !== '' ? $password : null;
    }

    /**
     * @param list<array<string, mixed>> $operations
     * @return array{content: string, changed: bool, outcomes: array<int, mixed>, sha256: string}
     */
    public function mutate(array $operations, string $fileContent): array {
        [$header, $payload, $sha256] = $this->requestProtocol([
            'command' => 'mutate',
            'operations' => $operations,
        ], $fileContent);

        return [
            'content' => $payload,
            'changed' => (bool)($header['changed'] ?? true),
            'outcomes' => is_array($header['outcomes'] ?? null)
                ? $header['outcomes']
                : [],
            'sha256' => $sha256,
        ];
    }

    /** @return array<string, mixed> */
    public function getAccountSnapshot(string $accountId, string $fileContent): array {
        return $this->requestJson([
            'command' => 'accountSnapshot',
            'accountId' => $accountId,
        ], $fileContent);
    }

    /** @return array<string, mixed> */
    public function getDocumentInfo(string $fileContent): array {
        return $this->requestJson([
            'command' => 'documentInfo',
        ], $fileContent);
    }

    public function checkGSBFile(string $fileContent): string {
        $info = $this->getDocumentInfo($fileContent);
        return json_encode([
            'Encrypted' => !empty($info['encrypted']) ? 'True' : 'False',
            'Compressed' => !empty($info['compressed']),
            'FileVersion' => $info['fileVersion'] ?? null,
            'GrisbiVersion' => $info['grisbiVersion'] ?? null,
        ], JSON_THROW_ON_ERROR);
    }

    public function getAccounts(string $fileContent): string {
        return $this->requestJsonPayload([
            'command' => 'listAccounts',
        ], $fileContent);
    }

    public function getParties(string $fileContent): string {
        return $this->requestJsonPayload([
            'command' => 'listParties',
        ], $fileContent);
    }

    public function getCategories(string $fileContent): string {
        return $this->requestJsonPayload([
            'command' => 'listCategories',
        ], $fileContent);
    }

    public function getTransactions(string $accountId, string $fileContent): string {
        return $this->requestJsonPayload([
            'command' => 'listTransactions',
            'accountId' => $accountId,
        ], $fileContent);
    }

    /** @deprecated Raw-attribute mutation is permanently disabled. */
    public function addTransactions(string $transactionDataJson, string $fileContent): string {
        unset($transactionDataJson, $fileContent);
        throw new \LogicException(
            'Raw Grisbi mutation is disabled; use typed mutation operations.'
        );
    }

    /**
     * @param array<string, mixed> $request
     * @return array<string, mixed>
     */
    private function requestJson(array $request, string $fileContent): array {
        $payload = $this->requestJsonPayload($request, $fileContent);
        $decoded = json_decode($payload, true, 512, JSON_THROW_ON_ERROR);
        if (!is_array($decoded)) {
            throw new \RuntimeException('Python returned an invalid JSON object.');
        }
        return $decoded;
    }

    /** @param array<string, mixed> $request */
    private function requestJsonPayload(array $request, string $fileContent): string {
        [$header, $payload] = $this->requestProtocol($request, $fileContent);
        if (($header['contentType'] ?? null) !== 'application/json') {
            throw new \RuntimeException(
                'Python returned an unexpected response content type.'
            );
        }
        return $payload;
    }

    /**
     * @param array<string, mixed> $request
     * @return array{0: array<string, mixed>, 1: string, 2: string}
     */
    private function requestProtocol(array $request, string $fileContent): array {
        $requestId = bin2hex(random_bytes(16));
        $request['version'] = ProtocolFrame::VERSION;
        $request['requestId'] = $requestId;
        $stdin = ProtocolFrame::encode($request, $fileContent);
        $stdout = $this->runProcess(
            [$this->pythonBinary, $this->protocolScriptPath],
            $stdin,
            $this->password
        );
        [$header, $payload] = ProtocolFrame::decode($stdout);

        if (($header['version'] ?? null) !== ProtocolFrame::VERSION) {
            throw new \RuntimeException('Python returned an unsupported protocol version.');
        }
        if (($header['requestId'] ?? null) !== $requestId) {
            throw new \RuntimeException('Python returned a mismatched protocol request ID.');
        }
        if (($header['ok'] ?? false) !== true) {
            $error = is_array($header['error'] ?? null) ? $header['error'] : [];
            $code = is_string($error['code'] ?? null)
                ? $error['code']
                : 'protocol-error';
            $message = is_string($error['message'] ?? null)
                ? $error['message']
                : 'The Grisbi process rejected the request.';
            throw new GrisbiProtocolException($code, $message, $error);
        }

        $expectedHash = $header['sha256'] ?? null;
        $actualHash = hash('sha256', $payload);
        if (!is_string($expectedHash) || !hash_equals($expectedHash, $actualHash)) {
            throw new \RuntimeException('Python response checksum verification failed.');
        }
        return [$header, $payload, $actualHash];
    }

    /** @param list<string> $command */
    private function runProcess(
        array $command,
        string $stdin,
        ?string $password
    ): string {
        $descriptors = [
            0 => ['pipe', 'r'],
            1 => ['pipe', 'w'],
            2 => ['pipe', 'w'],
            3 => ['pipe', 'r'],
        ];
        $pipes = [];
        $process = proc_open(
            $command,
            $descriptors,
            $pipes,
            null,
            null,
            ['bypass_shell' => true]
        );
        if (!is_resource($process)) {
            throw new \RuntimeException('Failed to start the Grisbi Python process.');
        }

        try {
            $this->writeAll($pipes[3], $password ?? '');
            fclose($pipes[3]);
            $this->writeAll($pipes[0], $stdin);
            fclose($pipes[0]);

            [$stdout, $stderr] = $this->readOutput(
                $pipes[1],
                $pipes[2],
                $this->processTimeoutSeconds
            );
            $exitCode = proc_close($process);
            $process = null;
            if ($exitCode !== 0) {
                $message = trim($stderr);
                if ($message === '') {
                    $message = 'Python exited with status ' . $exitCode . '.';
                }
                throw new \RuntimeException(
                    'Grisbi Python process failed: ' . substr($message, 0, 4096)
                );
            }
            return $stdout;
        } catch (\Throwable $e) {
            foreach ($pipes as $pipe) {
                if (is_resource($pipe)) {
                    fclose($pipe);
                }
            }
            if (is_resource($process)) {
                proc_terminate($process);
                proc_close($process);
            }
            throw $e;
        }
    }

    /** @param resource $stream */
    private function writeAll($stream, string $data): void {
        $offset = 0;
        $length = strlen($data);
        while ($offset < $length) {
            $written = fwrite($stream, substr($data, $offset));
            if ($written === false || $written === 0) {
                throw new \RuntimeException('Failed to write to the Python process.');
            }
            $offset += $written;
        }
    }

    /**
     * @param resource $stdoutStream
     * @param resource $stderrStream
     * @return array{0: string, 1: string}
     */
    private function readOutput(
        $stdoutStream,
        $stderrStream,
        int $timeoutSeconds
    ): array {
        stream_set_blocking($stdoutStream, false);
        stream_set_blocking($stderrStream, false);
        $streams = [
            'stdout' => $stdoutStream,
            'stderr' => $stderrStream,
        ];
        $stdout = '';
        $stderr = '';
        $deadline = microtime(true) + $timeoutSeconds;

        while ($streams !== []) {
            $read = array_values($streams);
            $write = null;
            $except = null;
            $selected = stream_select($read, $write, $except, 1);
            if ($selected === false) {
                throw new \RuntimeException('Failed while reading the Python process.');
            }
            if ($selected === 0) {
                if (microtime(true) >= $deadline) {
                    throw new \RuntimeException('The Grisbi Python process timed out.');
                }
                continue;
            }
            foreach ($read as $stream) {
                $chunk = stream_get_contents($stream);
                if ($chunk === false) {
                    throw new \RuntimeException('Failed to read the Python process output.');
                }
                if ($stream === $stdoutStream) {
                    $stdout .= $chunk;
                } else {
                    $stderr .= $chunk;
                }
                if (feof($stream)) {
                    $key = $stream === $stdoutStream ? 'stdout' : 'stderr';
                    fclose($stream);
                    unset($streams[$key]);
                }
            }
        }
        return [$stdout, $stderr];
    }
}
