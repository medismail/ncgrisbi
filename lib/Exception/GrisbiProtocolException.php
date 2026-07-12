<?php
declare(strict_types=1);

namespace OCA\NCGrisbi\Exception;

final class GrisbiProtocolException extends \RuntimeException {
    /**
     * @param array<string, mixed> $details
     */
    public function __construct(
        private string $protocolCode,
        string $message,
        private array $details = []
    ) {
        parent::__construct($message);
    }

    public function getProtocolCode(): string {
        return $this->protocolCode;
    }

    /**
     * @return array<string, mixed>
     */
    public function getDetails(): array {
        return $this->details;
    }
}
