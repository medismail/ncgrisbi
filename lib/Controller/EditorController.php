<?php
declare(strict_types=1);

namespace OCA\NCGrisbi\Controller;

use OCA\NCGrisbi\Exception\DocumentConflictException;
use OCA\NCGrisbi\Exception\DocumentNotFoundException;
use OCA\NCGrisbi\Exception\GrisbiProtocolException;
use OCA\NCGrisbi\Service\GsbDocumentService;
use OCP\AppFramework\Controller;
use OCP\AppFramework\Http\Attribute\NoAdminRequired;
use OCP\AppFramework\Http\JSONResponse;
use OCP\Files\InvalidPathException;
use OCP\Files\NotPermittedException;
use OCP\IRequest;
use OCP\Lock\LockedException;

final class EditorController extends Controller {
    public function __construct(
        string $appName,
        IRequest $request,
        private GsbDocumentService $documentService
    ) {
        parent::__construct($appName, $request);
    }

    /**
     * Return the typed normal-transaction editor snapshot and its matching ETag.
     * This endpoint intentionally keeps normal Nextcloud CSRF validation.
     */
    #[NoAdminRequired]
    public function account(
        string $accountId,
        string $filePath,
        string $filePassword = ''
    ): JSONResponse {
        try {
            $result = $this->documentService->getAccountSnapshot(
                $filePath,
                $accountId,
                $filePassword !== '' ? $filePassword : null
            );
            return new JSONResponse([
                'success' => true,
                'document' => $result['document'],
                'snapshot' => $result['snapshot'],
            ]);
        } catch (\Throwable $error) {
            return $this->errorResponse($error);
        }
    }

    private function errorResponse(\Throwable $error): JSONResponse {
        if ($error instanceof DocumentConflictException) {
            return new JSONResponse([
                'success' => false,
                'code' => 'etag-conflict',
                'message' => $error->getMessage(),
                'currentEtag' => $error->getCurrentEtag(),
            ], 409);
        }
        if ($error instanceof DocumentNotFoundException) {
            return new JSONResponse([
                'success' => false,
                'code' => 'document-not-found',
                'message' => $error->getMessage(),
            ], 404);
        }
        if ($error instanceof GrisbiProtocolException) {
            $code = $error->getProtocolCode();
            $status = match ($code) {
                'record-not-found' => 404,
                'invalid-protocol', 'internal-error' => 500,
                default => 422,
            };
            return new JSONResponse([
                'success' => false,
                'code' => $code,
                'message' => $error->getMessage(),
                'details' => $error->getDetails(),
            ], $status);
        }
        if ($error instanceof LockedException) {
            return new JSONResponse([
                'success' => false,
                'code' => 'document-locked',
                'message' => 'The GSB file is currently locked by another operation.',
            ], 423);
        }
        if ($error instanceof NotPermittedException) {
            return new JSONResponse([
                'success' => false,
                'code' => 'permission-denied',
                'message' => 'The GSB file cannot be read.',
            ], 403);
        }
        if ($error instanceof InvalidPathException || $error instanceof \InvalidArgumentException) {
            return new JSONResponse([
                'success' => false,
                'code' => 'invalid-request',
                'message' => $error->getMessage(),
            ], 400);
        }
        if ($error instanceof \JsonException) {
            return new JSONResponse([
                'success' => false,
                'code' => 'invalid-python-response',
                'message' => 'The Grisbi snapshot worker returned invalid JSON.',
            ], 500);
        }
        return new JSONResponse([
            'success' => false,
            'code' => 'internal-error',
            'message' => 'The GSB snapshot operation failed.',
        ], 500);
    }
}
