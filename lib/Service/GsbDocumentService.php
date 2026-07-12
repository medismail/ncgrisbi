<?php
declare(strict_types=1);

namespace OCA\NCGrisbi\Service;

use OCA\NCGrisbi\Exception\DocumentConflictException;
use OCA\NCGrisbi\Exception\DocumentNotFoundException;
use OCA\NCGrisbi\Grisbi\GrisbiProcess;
use OCP\Files\File;
use OCP\Files\Folder;
use OCP\Files\IRootFolder;
use OCP\Files\NotFoundException;
use OCP\IUserSession;
use OCP\Lock\ILockingProvider;

final class GsbDocumentService {
    private const ENCRYPTION_V2_MARKER = 'Grisbi encryption v2: ';
    private ?Folder $userFolder = null;

    public function __construct(
        IRootFolder $rootFolder,
        IUserSession $userSession,
        private GrisbiProcess $grisbiProcess,
        private ILockingProvider $lockingProvider
    ) {
        $user = $userSession->getUser();
        if ($user !== null) {
            $this->userFolder = $rootFolder->getUserFolder($user->getUID());
        }
    }

    public function readContent(string $filePath): string {
        return $this->getFile($filePath)->getContent();
    }

    /**
     * @return array{fileId: int, path: string, etag: string, size: int|float, compressed: bool, encrypted: bool}
     */
    public function getState(string $filePath): array {
        $file = $this->getFile($filePath);
        $content = $file->getContent();
        $envelope = $this->inspectEnvelope($content);
        return [
            'fileId' => (int)$file->getId(),
            'path' => $this->normalizePath($filePath),
            'etag' => (string)$file->getEtag(),
            'size' => $file->getSize(),
            'compressed' => $envelope['compressed'],
            'encrypted' => $envelope['encrypted'],
        ];
    }

    /**
     * @param list<array<string, mixed>> $operations
     * @return array{fileId: int, etag: string, changed: bool, outcomes: array<int, mixed>, sha256: string}
     */
    public function mutate(
        string $filePath,
        string $baseEtag,
        array $operations,
        ?string $password = null
    ): array {
        if ($baseEtag === '') {
            throw new \InvalidArgumentException('baseEtag is required.');
        }
        if ($operations === []) {
            throw new \InvalidArgumentException('At least one mutation operation is required.');
        }

        $file = $this->getFile($filePath);
        $lockKey = 'ncgrisbi:document:' . (string)$file->getId();
        $locked = false;
        try {
            // This application-scoped lock serializes every NCGrisbi mutation
            // without recursively locking the file before File::putContent(),
            // which acquires Nextcloud's filesystem lock internally.
            $this->lockingProvider->acquireLock(
                $lockKey,
                ILockingProvider::LOCK_EXCLUSIVE
            );
            $locked = true;

            $currentEtag = (string)$file->getEtag();
            if (!hash_equals($currentEtag, $baseEtag)) {
                throw new DocumentConflictException($currentEtag);
            }

            $original = $file->getContent();
            $this->grisbiProcess->setPassword($password ?? '');
            $result = $this->grisbiProcess->mutate($operations, $original);
            $output = $result['content'];
            $bytesChanged = !hash_equals(
                hash('sha256', $original),
                hash('sha256', $output)
            );
            if ($result['changed'] !== $bytesChanged) {
                throw new \RuntimeException(
                    'The Python changed flag does not match the returned bytes.'
                );
            }

            if ($bytesChanged) {
                // Catch external writes that occurred while Python validated the
                // batch. File::putContent() then performs one normal Nextcloud
                // write, including its hooks and filesystem locking.
                $beforeWriteEtag = (string)$file->getEtag();
                if (!hash_equals($currentEtag, $beforeWriteEtag)) {
                    throw new DocumentConflictException($beforeWriteEtag);
                }
                $file->putContent($output);
            }

            return [
                'fileId' => (int)$file->getId(),
                'etag' => (string)$file->getEtag(),
                'changed' => $bytesChanged,
                'outcomes' => $result['outcomes'],
                'sha256' => $result['sha256'],
            ];
        } finally {
            if ($locked) {
                $this->lockingProvider->releaseLock(
                    $lockKey,
                    ILockingProvider::LOCK_EXCLUSIVE
                );
            }
        }
    }

    private function getFile(string $filePath): File {
        if ($this->userFolder === null) {
            throw new DocumentNotFoundException(
                'No authenticated user folder is available.'
            );
        }
        $path = $this->normalizePath($filePath);
        try {
            $node = $this->userFolder->get($path);
        } catch (NotFoundException $e) {
            throw new DocumentNotFoundException(
                'The requested GSB file does not exist.',
                0,
                $e
            );
        }
        if (!$node instanceof File) {
            throw new DocumentNotFoundException('The requested path is not a file.');
        }
        return $node;
    }

    private function normalizePath(string $filePath): string {
        $path = ltrim(trim($filePath), '/');
        if ($path === '' || str_contains($path, "\0")) {
            throw new \InvalidArgumentException('filePath is invalid.');
        }
        foreach (explode('/', $path) as $segment) {
            if ($segment === '' || $segment === '.' || $segment === '..') {
                throw new \InvalidArgumentException(
                    'filePath contains an invalid segment.'
                );
            }
        }
        return $path;
    }

    /** @return array{compressed: bool, encrypted: bool} */
    private function inspectEnvelope(string $content): array {
        $compressed = str_starts_with($content, "\x1f\x8b");
        $payload = $content;
        if ($compressed) {
            $decoded = gzdecode($content);
            if ($decoded === false) {
                throw new \RuntimeException('The GSB gzip envelope is invalid.');
            }
            $payload = $decoded;
        }
        return [
            'compressed' => $compressed,
            'encrypted' => str_starts_with(
                $payload,
                self::ENCRYPTION_V2_MARKER
            ),
        ];
    }
}
