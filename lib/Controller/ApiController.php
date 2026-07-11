<?php
declare(strict_types=1);

namespace OCA\NCGrisbi\Controller;

use OCP\AppFramework\Controller;
use OCP\AppFramework\Http\JSONResponse;
use OCP\IRequest;
use OCP\Files\IRootFolder;
use OCP\Files\FileInfo;
use OCP\Files\Node;
use OCP\Files\NotFoundException;
use OCP\Files\InvalidPathException;
use OCP\Files\NotPermittedException;
use OCP\Appframework\Http\Attribute\NoCSRFRequired;
use OCP\AppFramework\Http\Attribute\NoAdminRequired;
use OCA\NCGrisbi\Tools\Helper;
use OCA\NCGrisbi\Grisbi\GrisbiProcess;
use OCA\NCGrisbi\Storage\StorageHandle;

class ApiController extends Controller {
    private $userId;
    private $userFolder;

    public function __construct(
        $appName,
        IRequest $request,
        IRootFolder $rootFolder,
        string $userId
    ) {
        parent::__construct($appName, $request);
        $this->userId = $userId;
        $this->userFolder = $rootFolder->getUserFolder($userId);
    }

    public function readFile(string $filePath): ?string {
        try {
            $file = $this->userFolder->get($filePath);
            if ($file instanceof Node && !($file->getType() === FileInfo::TYPE_FOLDER)) {
                return $file->getContent();
            }
        } catch (NotFoundException $e) {
            return null;
        }
        return null;
    }

    /**
     *
     * @param string $userId L'ID de l'utilisateur.
     * @param string $filePath Chemin du fichier (ex: "Documents/mon_fichier.txt").
     * @param string $content Contenu à écrire dans le fichier.
     * @param bool $overwrite Si `true`, écrase le fichier s'il existe déjà.
     * @return bool `true` si l'écriture a réussi, `false` sinon.
     * @throws \RuntimeException Si une erreur critique survient.
     */
    public function writeFile(string $filePath, string $content, bool $overwrite = false): bool
    {
        try {
            $node = $this->userFolder->get($filePath);

            if ($node->getType() === FileInfo::TYPE_FOLDER) {
                throw new \RuntimeException("Le chemin '$filePath' est un dossier, pas un fichier.");
            }

            if (!$overwrite) {
                throw new \RuntimeException("Le fichier '$filePath' existe déjà et l'option overwrite est désactivée.");
            }

            $node->putContent($content);
            return true;

        } catch (NotFoundException $e) {
            $parentPath = dirname($filePath);
            if ($parentPath !== '.') {
                try {
                    $parentFolder = $this->userFolder->newFolder($parentPath);
                } catch (InvalidPathException $e) {
                    throw new \RuntimeException("Chemin invalide pour le dossier parent : '$parentPath'.");
                }
            }

            $file = $this->userFolder->newFile($filePath);
            $file->putContent($content);
            return true;

        } catch (NotPermittedException $e) {
            throw new \RuntimeException("Permission refusée pour écrire dans '$filePath'.");
        } catch (\Exception $e) {
            throw new \RuntimeException("Erreur lors de l'écriture du fichier '$filePath' : " . $e->getMessage());
        }
    }


    /**
     * @param string $filePath
     * @param string $filePassword
     *
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function getParties(string $filePath, string $filePassword): JSONResponse {
        //if (Helper::pythonInstalled()) {
            $contents = $this->readFile($filePath);
            $process = new GrisbiProcess();
            $process->setPassword($filePassword);
            $parties = json_decode($process->getParties($contents), true);
            return new JSONResponse($parties);
        //}
        //return new JSONResponse([]); // Return an empty array if Python is not installed
    }

    /**
     * @param string $filePath
     * @param string $filePassword
     *
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function getCategories(string $filePath, string $filePassword): JSONResponse {
        //if (Helper::pythonInstalled()) {
            $contents = $this->readFile($filePath);
            $process = new GrisbiProcess();
            $process->setPassword($filePassword);
            $categories = json_decode($process->getCategories($contents), true);
            return new JSONResponse($categories);
        //}
        //return new JSONResponse([]); // Return an empty array if Python is not installed
    }

    /**
     * @param string $filePath
     * @param string $filePassword
     *
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function getAccounts(string $filePath, string $filePassword): JSONResponse {
        //if (Helper::pythonInstalled()) {
            /*$retval = null;
            $data = null;
            exec('python3 ' . __DIR__ . '/../bin/grisbi.py ' . '--list-accounts ' . __DIR__ . $filePath, $data, $retval);*/
            //$real = __DIR__ . $filePath;
            $contents = $this->readFile($filePath);
            $process = new GrisbiProcess();
            $process->setPassword($filePassword);
            $accounts = json_decode($process->getAccounts($contents), true);
            return new JSONResponse($accounts);
        //}
        //return new JSONResponse('');
    }

    /**
     * @param int $accountId
     * @param string $filePath
     * @param string $filePassword
     *
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function getTransactions(string $accountId, string $filePath, string $filePassword): JSONResponse {
        //if (Helper::pythonInstalled()) {
            $contents = $this->readFile($filePath);
            $process = new GrisbiProcess();
            $process->setPassword($filePassword);
            $transactions = json_decode($process->getTransactions($accountId, $contents), true);
            return new JSONResponse($transactions);
        //}
        //return new JSONResponse('');
    }

    /**
     * @param string $filePath
     *
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function checkEncrypted(string $filePath): JSONResponse {
        //if (Helper::pythonInstalled()) {
            $contents = $this->readFile($filePath);
            $process = new GrisbiProcess();
            $accounts = json_decode($process->checkGSBFile($contents), true);
            return new JSONResponse($accounts);
        //}
        //return new JSONResponse('');
    }

    /**
     * @param string $filePath
     * @param string $filePassword
     * @param string $transactionDataJson
     *
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function saveTransaction(string $filePath, string $filePassword, string $transactionDataJson): JSONResponse {
        //if (Helper::pythonInstalled()) {
            $contents = $this->readFile($filePath);
            $process = new GrisbiProcess();
            $process->setPassword($filePassword);
            $output = $process->addTransactions($transactionDataJson, $contents);
            try {
                $success = $this->writeFile($filePath, $output, true);
                return new JSONResponse(['success' => $success, 'output' => 'TBD']); // You might want to return a more structured response
            } catch (\RuntimeException $e) {
                return new JSONResponse(['success' => false, 'output' => $e->getMessage()]);
            }
        //}
        //return new JSONResponse(['success' => false, 'message' => 'Python not installed']);
    }
}
