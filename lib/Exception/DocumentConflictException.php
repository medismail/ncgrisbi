<?php
declare(strict_types=1);

namespace OCA\NCGrisbi\Exception;

final class DocumentConflictException extends \RuntimeException {
    public function __construct(private string $currentEtag) {
        parent::__construct('The GSB file changed after it was loaded.');
    }

    public function getCurrentEtag(): string {
        return $this->currentEtag;
    }
}
