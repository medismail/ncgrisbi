<?php
declare(strict_types=1);

namespace OCA\NCGrisbi\Grisbi;

use OCA\NCGrisbi\Exception\GrisbiProtocolException;

final class GrisbiProcess {
    private string $pythonBinary;
    private string $legacyWrapperPath;
    private string $protocolScriptPath;
    private ?string $password = null;
    private int $processTimeoutSeconds = 120;

    public function __construct() {
        $this->pythonBinary = 'python3';
        $this->legacyWrapperPath = __DIR__ . '/../bin/ncgrisbi_legacy.py';
        $this->protocolScriptPath = __DIR__ . '/../bin/ncgrisbi_protocol.py';
    }

    public static function createForTesting(
        string $pythonBinary,
        string $legacyWrapperPath,
        string $protocolScriptPath,
        int $processTimeoutSeconds = 10
    ): self {
        $instance = new self();
        $instance->pythonBinary = $pythonBinary;
        $instance->legacyWrapperPath = $legacyWrapperPath;
        $instance->protocolScriptPath = $protocolScriptPath;
        $instance->processTimeoutSeconds = $processTimeoutSeconds;
        return $instance;
    }

    public function setPassword(string $password): void {
        $this->password = $password !== '' ? $password : null;
    }

    /**
     * Compatibility entry point for the existing read-only API.
     *
     * The password is transported through descriptor 3 by the wrapper and never
     * appears in the operating-system command line or process environment.
     *
     * @param list<string> $parameters
     */
    public function run(
        array $parameters = [],
        $inputfile = null,
        ?callable $inputHandler = null
    ): string {
        if ($inputHandler !== null) {
            throw new \InvalidArgumentException(
                'Interactive process prompts are disabled; use descriptor 3.'
            );
        }
        $command = array_merge(
            [$this->pythonBinary, $this->legacyWrapperPath],
            array_map(static fn($value): string => (string)$value, $parameters)
        );
        return $this->runProcess(
            $command,
            is_string($inputfile) ? $inputfile : '',
            $this->password
        );
    }

    /**
     * @param list<array<string, mixed>> $operations
     * @return array{content: string, changed: bool, outcomes: array<int, mixed>, sha256: string}
     */
    public function mutate(array $operations, string $fileContent): array {
        $requestId = bin2hex(random_bytes(16));
        $request = [
            'version' => ProtocolFrame::VERSION,
            'command' => 'mutate',
            'requestId' => $requestId,
            'operations' => $operations,
        ];
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
                : 'The Grisbi mutation process rejected the request.';
            throw new GrisbiProtocolException($code, $message, $error);
        }

        $expectedHash = $header['sha256'] ?? null;
        $actualHash = hash('sha256', $payload);
        if (!is_string($expectedHash) || !hash_equals($expectedHash, $actualHash)) {
            throw new \RuntimeException('Python response checksum verification failed.');
        }

        return [
            'content' => $payload,
            'changed' => (bool)($header['changed'] ?? true),
            'outcomes' => is_array($header['outcomes'] ?? null)
                ? $header['outcomes']
                : [],
            'sha256' => $actualHash,
        ];
    }

    public function checkGSBFile(string $fileContent): string {
        return $this->run(['--check-file', '-'], $fileContent);
    }

    public function getAccounts(string $fileContent): string {
        return $this->run(['--list-accounts', '-'], $fileContent);
    }

    public function getParties(string $fileContent): string {
        return $this->run(['--list-parties', '-'], $fileContent);
    }

    public function getCategories(string $fileContent): string {
        return $this->run(['--list-categories', '-'], $fileContent);
    }

    public function getTransactions(string $accountId, string $fileContent): string {
        return $this->run(['--list-transactions', $accountId, '-'], $fileContent);
    }

    /**
     * @deprecated The raw transaction API is disabled by ApiController in Phase 3.
     */
    public function addTransactions(string $transactionDataJson, string $fileContent): string {
        return $this->run(
            ['--add-transaction', '--transaction-data', $transactionDataJson, '-'],
            $fileContent
        );
    }

    /**
     * @param list<string> $command
     */
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
            // Write the small password pipe first. This avoids a deadlock when a
            // worker reads descriptor 3 before consuming a large stdin payload.
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
