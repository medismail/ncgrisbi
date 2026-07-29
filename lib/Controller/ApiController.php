<?php
declare(strict_types=1);

namespace OCA\NCGrisbi\Controller;

use OCA\NCGrisbi\Exception\DocumentConflictException;
use OCA\NCGrisbi\Exception\DocumentNotFoundException;
use OCA\NCGrisbi\Exception\GrisbiProtocolException;
use OCA\NCGrisbi\Grisbi\GrisbiProcess;
use OCA\NCGrisbi\Service\GsbDocumentService;
use OCP\AppFramework\Controller;
use OCP\AppFramework\Http\JSONResponse;
use OCP\AppFramework\Http\Attribute\NoAdminRequired;
use OCP\AppFramework\Http\Attribute\NoCSRFRequired;
use OCP\Files\InvalidPathException;
use OCP\Files\NotPermittedException;
use OCP\IRequest;
use OCP\Lock\LockedException;

final class ApiController extends Controller {
    public function __construct(
        string $appName,
        IRequest $request,
        private GrisbiProcess $grisbiProcess,
        private GsbDocumentService $documentService
    ) {
        parent::__construct($appName, $request);
    }

    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function getParties(string $filePath, string $filePassword = ''): JSONResponse {
        return $this->legacyRead(
            $filePath,
            $filePassword,
            fn(string $content): string => $this->grisbiProcess->getParties($content)
        );
    }

    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function getCategories(string $filePath, string $filePassword = ''): JSONResponse {
        return $this->legacyRead(
            $filePath,
            $filePassword,
            fn(string $content): string => $this->grisbiProcess->getCategories($content)
        );
    }

    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function getAccounts(string $filePath, string $filePassword = ''): JSONResponse {
        return $this->legacyRead(
            $filePath,
            $filePassword,
            fn(string $content): string => $this->grisbiProcess->getAccounts($content)
        );
    }

    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function getTransactions(
        string $accountId,
        string $filePath,
        string $filePassword = ''
    ): JSONResponse {
        return $this->legacyRead(
            $filePath,
            $filePassword,
            fn(string $content): string => $this->grisbiProcess->getTransactions(
                $accountId,
                $content
            )
        );
    }

    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function checkEncrypted(string $filePath): JSONResponse {
        try {
            $state = $this->documentService->getState($filePath);
            return new JSONResponse([
                'Encrypted' => $state['encrypted'] ? 'True' : 'False',
                'Compressed' => $state['compressed'],
                'etag' => $state['etag'],
            ]);
        } catch (\Throwable $e) {
            return $this->errorResponse($e);
        }
    }

    /**
     * Return the concurrency token and envelope metadata used by the mutation API.
     */
    #[NoAdminRequired]
    public function documentState(string $filePath): JSONResponse {
        try {
            return new JSONResponse([
                'success' => true,
                'document' => $this->documentService->getState($filePath),
            ]);
        } catch (\Throwable $e) {
            return $this->errorResponse($e);
        }
    }

    /**
     * Apply one typed mutation batch with optimistic concurrency protection.
     *
     * This endpoint intentionally has no NoCSRFRequired attribute. Nextcloud's
     * request token is mandatory for every state-changing request.
     *
     * @param list<array<string, mixed>> $operations
     */
    #[NoAdminRequired]
    public function mutate(
        string $filePath,
        string $baseEtag,
        array $operations,
        string $filePassword = ''
    ): JSONResponse {
        try {
            $result = $this->documentService->mutate(
                $filePath,
                $baseEtag,
                $operations,
                $filePassword !== '' ? $filePassword : null
            );
            return new JSONResponse([
                'success' => true,
                'document' => $result,
            ]);
        } catch (\Throwable $e) {
            return $this->errorResponse($e);
        }
    }

    /**
     * The original endpoint accepted raw GSB attributes, had no client ETag and
     * rewrote the full XML tree. It is disabled so an old client cannot bypass
     * the Phase 2 validator and Phase 3 concurrency contract.
     */
    #[NoAdminRequired]
    public function saveTransaction(
        string $filePath,
        string $filePassword,
        string $transactionDataJson
    ): JSONResponse {
        return new JSONResponse([
            'success' => false,
            'code' => 'legacy-mutation-disabled',
            'message' => 'Use /api/mutations with baseEtag and typed operations.',
        ], 410);
    }

    /**
     * @param callable(string): string $operation
     */
    private function legacyRead(
        string $filePath,
        string $filePassword,
        callable $operation
    ): JSONResponse {
        try {
            $content = $this->getFileContent($filePath);
            $this->grisbiProcess->setPassword($filePassword);
            $json = $operation($content);
            $decoded = json_decode($json, true, 512, JSON_THROW_ON_ERROR);
            return new JSONResponse($decoded);
        } catch (\Throwable $e) {
            return $this->errorResponse($e);
        }
    }

    private function getFileContent(string $filePath): string {
        return $this->documentService->readContent($filePath);
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
                'mutation-conflict' => 409,
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
                'message' => 'The GSB file cannot be read or updated.',
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
                'message' => 'The Grisbi reader returned invalid JSON.',
            ], 500);
        }
        return new JSONResponse([
            'success' => false,
            'code' => 'internal-error',
            'message' => 'The GSB operation failed.',
        ], 500);
    }
}
