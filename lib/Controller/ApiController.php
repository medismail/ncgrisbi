<?php
declare(strict_types=1);

namespace OCA\NCGrisbi\Controller;

use OCP\AppFramework\Controller;
use OCP\AppFramework\Http\JSONResponse;
use OCP\IRequest;
use OCP\Appframework\Http\Attribute\NoCSRFRequired;
use OCP\AppFramework\Http\Attribute\NoAdminRequired;
use OCA\NCGrisbi\Tools\Helper;
use OCA\NCGrisbi\Grisbi\GrisbiProcess;
use OCA\NCGrisbi\Storage\StorageHandle;

class ApiController extends Controller {
    private $userId;

    public function __construct(
        $appName,
        IRequest $request,
        $UserId
    ) {
        parent::__construct($appName, $request);
        $this->userId = $UserId;
    }

    /**
     * @param string $filePath
     * @param string $filePassword
     *
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function getParties(string $filePath, string $filePassword): JSONResponse {
        if (Helper::pythonInstalled()) {
            $rootFolder = \OC::$server->getRootFolder();
            $storageHandle = new StorageHandle($rootFolder);
            $contents = $storageHandle->readFile($this->userId, $filePath);
            $process = new GrisbiProcess();
            $process->setPassword($filePassword);
            $parties = json_decode($process->getParties($contents), true);
            return new JSONResponse($parties);
        }
        return new JSONResponse([]); // Return an empty array if Python is not installed
    }

    /**
     * @param string $filePath
     * @param string $filePassword
     *
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function getCategories(string $filePath, string $filePassword): JSONResponse {
        if (Helper::pythonInstalled()) {
            $rootFolder = \OC::$server->getRootFolder();
            $storageHandle = new StorageHandle($rootFolder);
            $contents = $storageHandle->readFile($this->userId, $filePath);
            $process = new GrisbiProcess();
            $process->setPassword($filePassword);
            $categories = json_decode($process->getCategories($contents), true);
            return new JSONResponse($categories);
        }
        return new JSONResponse([]); // Return an empty array if Python is not installed
    }

    /**
     * @param string $filePath
     * @param string $filePassword
     *
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function getAccounts(string $filePath, string $filePassword): JSONResponse {
        if (Helper::pythonInstalled()) {
            /*$retval = null;
            $data = null;
            exec('python3 ' . __DIR__ . '/../bin/grisbi.py ' . '--list-accounts ' . __DIR__ . $filePath, $data, $retval);*/
            //$real = __DIR__ . $filePath;
            $rootFolder = \OC::$server->getRootFolder();
            $storageHandle = new StorageHandle($rootFolder);
            $contents = $storageHandle->readFile($this->userId, $filePath);
            $process = new GrisbiProcess();
            $process->setPassword($filePassword);
            $accounts = json_decode($process->getAccounts($contents), true);
            return new JSONResponse($accounts);
        }
        return new JSONResponse('');
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
        if (Helper::pythonInstalled()) {
            $rootFolder = \OC::$server->getRootFolder();
            $storageHandle = new StorageHandle($rootFolder);
            $contents = $storageHandle->readFile($this->userId, $filePath);
            $process = new GrisbiProcess();
            $process->setPassword($filePassword);
            $transactions = json_decode($process->getTransactions($accountId, $contents), true);
            return new JSONResponse($transactions);
        }
        return new JSONResponse('');
    }

    /**
     * @param string $filePath
     *
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function checkEncrypted(string $filePath): JSONResponse {
        if (Helper::pythonInstalled()) {
            $rootFolder = \OC::$server->getRootFolder();
            $storageHandle = new StorageHandle($rootFolder);
            $contents = $storageHandle->readFile($this->userId, $filePath);
            $process = new GrisbiProcess();
            $accounts = json_decode($process->checkGSBFile($contents), true);
            return new JSONResponse($accounts);
        }
        return new JSONResponse('');
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
        if (Helper::pythonInstalled()) {
            $rootFolder = \OC::$server->getRootFolder();
            $storageHandle = new StorageHandle($rootFolder);
            $contents = $storageHandle->readFile($this->userId, $filePath);
            $process = new GrisbiProcess();
            $process->setPassword($filePassword);
            $output = $process->addTransactions($transactionDataJson, $contents);
            $storageHandle->writeFile($this->userId, $filePath, $output);
            return new JSONResponse(['success' => true, 'output' => 'TBD']); // You might want to return a more structured response
        }
        return new JSONResponse(['success' => false, 'message' => 'Python not installed']);
    }
}
