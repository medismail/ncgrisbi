<?php
declare(strict_types=1);

namespace OCA\NCGrisbi\Listener;

use OCA\Files\Event\LoadAdditionalScriptsEvent;
use OCA\NCGrisbi\AppInfo\Application;
use OCP\EventDispatcher\Event;
use OCP\EventDispatcher\IEventListener;
use OCP\Util;

/**
 * Register the Files action before the Files UI starts initializing.
 *
 * @implements IEventListener<LoadAdditionalScriptsEvent>
 */
final class LoadAdditionalListener implements IEventListener {
    public function handle(Event $event): void {
        if (!$event instanceof LoadAdditionalScriptsEvent) {
            return;
        }

        Util::addInitScript(Application::APP_ID, 'viewer');
    }
}
