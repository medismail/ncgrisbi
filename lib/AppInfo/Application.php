<?php
declare(strict_types=1);

namespace OCA\NCGrisbi\AppInfo;

use OCP\AppFramework\App;
use OCP\AppFramework\Bootstrap\IBootContext;
use OCP\AppFramework\Bootstrap\IBootstrap;
use OCP\AppFramework\Bootstrap\IRegistrationContext;
use OCP\Files\IMimeTypeDetector;
use OCP\Util;

class Application extends App implements IBootstrap {
    public const APP_ID = 'ncgrisbi';

    public function __construct(array $params = []) {
        parent::__construct(self::APP_ID, $params);

        if (array_key_exists("REQUEST_URI", \OC::$server->getRequest()->server))
        {
            $url = \OC::$server->getRequest()->server["REQUEST_URI"];
            if (isset($url)) {
                if (preg_match("%/apps/files(/.*)?%", $url) || str_contains($url, "/s/")) // Files app and file sharing
                {
                    Util::addScript(self::APP_ID, "viewer");
                }
            }
        }

        $container = $this->getContainer();

        /**
         * Controllers
         */

        $container->registerService('Config', function ($c) {
            return $c->query('ServerContainer')->getConfig();
        });

        $detector = $container->query(IMimeTypeDetector::class);
        $detector->getAllMappings();
        $detector->registerType("gsb", "application/x-gsb");
    }

    public function register(IRegistrationContext $context): void {
    /*    $context->registerPage('PageController');
        $context->registerService('ApiController');*/
    }

    public function boot(IBootContext $context): void {
        Util::addScript(self::APP_ID, "viewer");
    }
}
