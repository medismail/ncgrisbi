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

final class ReportController extends Controller {
    public function __construct(
        string $appName,
        IRequest $request,
        private GsbDocumentService $documentService
    ) {
        parent::__construct($appName, $request);
    }

    /** Read-only report snapshot. The request still uses Nextcloud CSRF protection. */
    #[NoAdminRequired]
    public function snapshot(
        string $reportId,
        string $filePath,
        string $filePassword = ''
    ): JSONResponse {
        try {
            $result = $this->documentService->getReportSnapshot(
                $filePath,
                $reportId,
                $filePassword !== '' ? $filePassword : null
            );
            return new JSONResponse([
                'success' => true,
                'document' => $result['document'],
                'snapshot' => $result['snapshot'],
            ]);
        } catch (\Throwable $error) {
            if ($error instanceof DocumentConflictException) {
                return new JSONResponse([
                    'success' => false, 'code' => 'etag-conflict',
                    'message' => $error->getMessage(),
                    'currentEtag' => $error->getCurrentEtag(),
                ], 409);
            }
            if ($error instanceof DocumentNotFoundException) {
                return new JSONResponse([
                    'success' => false, 'code' => 'document-not-found',
                    'message' => $error->getMessage(),
                ], 404);
            }
            if ($error instanceof GrisbiProtocolException) {
                $code = $error->getProtocolCode();
                return new JSONResponse([
                    'success' => false, 'code' => $code,
                    'message' => $error->getMessage(),
                    'details' => $error->getDetails(),
                ], match ($code) {
                    'record-not-found' => 404,
                    'invalid-protocol', 'internal-error' => 500,
                    default => 422,
                });
            }
            if ($error instanceof LockedException) {
                return new JSONResponse([
                    'success' => false, 'code' => 'document-locked',
                    'message' => 'The GSB file is currently locked.',
                ], 423);
            }
            if ($error instanceof NotPermittedException) {
                return new JSONResponse([
                    'success' => false, 'code' => 'permission-denied',
                    'message' => 'The GSB file cannot be read.',
                ], 403);
            }
            if ($error instanceof InvalidPathException || $error instanceof \InvalidArgumentException) {
                return new JSONResponse([
                    'success' => false, 'code' => 'invalid-request',
                    'message' => $error->getMessage(),
                ], 400);
            }
            return new JSONResponse([
                'success' => false, 'code' => 'internal-error',
                'message' => 'The report operation failed.',
            ], 500);
        }
    }
}
