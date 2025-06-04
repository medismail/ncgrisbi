<?php

namespace OCA\NCGrisbi\Storage;

use OCP\Files\IRootFolder;
use OCP\Files\NotFoundException;
use OCP\Files\NotPermittedException;

class StorageHandle {
    private IRootFolder $storage;

    public function __construct(IRootFolder $storage) {
        $this->storage = $storage;
    }

    /**
     * Read the contents of a file from the given file path.
     *
     * @param string $filePath The path to the file to read.
     * @return string The contents of the file.
     * @throws NotFoundException If the file does not exist.
     * @throws NotPermittedException If the user does not have permission to read the file.
     */
    public function readFile($userId, $filePath) {
        $userFolder = $this->storage->getUserFolder($userId);
        $file = $userFolder->get($filePath);
        if ($file instanceof \OCP\Files\File) {
            return $file->getContent();
        } else {
            throw new StorageException('File not found: $filePath');
        }
    }

    /**
     * Write the given contents to the file at the specified file path.
     *
     * @param string $filePath The path to the file to write.
     * @param string $contents The contents to write to the file.
     * @throws NotPermittedException If the user does not have permission to write to the file.
     */
    public function writeFile($userId, $filePath, $contents) {
        $userFolder = $this->storage->getUserFolder($userId);
        try {
            $file = $userFolder->get($filePath);
        } catch(\OCP\Files\NotFoundException $e) {
            $userFolder->touch($filePath);
            $file = $userFolder->get($filePath);
        }
        $file->putContent($contents);
    }
}
