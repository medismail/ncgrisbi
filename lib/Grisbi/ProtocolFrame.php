<?php
declare(strict_types=1);

namespace OCA\NCGrisbi\Grisbi;

final class ProtocolFrame {
    public const VERSION = 1;
    private const MAX_HEADER_BYTES = 8388608;

    /**
     * @param array<string, mixed> $header
     */
    public static function encode(array $header, string $payload = ''): string {
        $header['payloadLength'] = strlen($payload);
        try {
            $json = json_encode(
                $header,
                JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE
            );
        } catch (\JsonException $e) {
            throw new \InvalidArgumentException('Protocol header is not JSON serializable.', 0, $e);
        }
        if (strlen($json) > self::MAX_HEADER_BYTES) {
            throw new \InvalidArgumentException('Protocol header exceeds the size limit.');
        }
        return pack('N', strlen($json)) . $json . $payload;
    }

    /**
     * @return array{0: array<string, mixed>, 1: string}
     */
    public static function decode(string $frame): array {
        if (strlen($frame) < 4) {
            throw new \RuntimeException('Protocol frame is truncated.');
        }
        $lengthData = unpack('Nlength', substr($frame, 0, 4));
        $headerLength = (int)($lengthData['length'] ?? 0);
        if ($headerLength <= 0 || $headerLength > self::MAX_HEADER_BYTES) {
            throw new \RuntimeException('Protocol header length is invalid.');
        }
        if (strlen($frame) < 4 + $headerLength) {
            throw new \RuntimeException('Protocol header is truncated.');
        }
        $headerJson = substr($frame, 4, $headerLength);
        try {
            $header = json_decode($headerJson, true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $e) {
            throw new \RuntimeException('Protocol header is not valid JSON.', 0, $e);
        }
        if (!is_array($header)) {
            throw new \RuntimeException('Protocol header must be a JSON object.');
        }
        $payload = substr($frame, 4 + $headerLength);
        $expectedLength = $header['payloadLength'] ?? null;
        if (!is_int($expectedLength) || $expectedLength < 0) {
            throw new \RuntimeException('Protocol payloadLength is invalid.');
        }
        if ($expectedLength !== strlen($payload)) {
            throw new \RuntimeException('Protocol payload length does not match payloadLength.');
        }
        return [$header, $payload];
    }
}
