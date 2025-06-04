<?php

/**
 *
 * NCGrisbi APP (Nextcloud)
 *
 * @author Mohamed-Ismail MEJRI <imejri@hotmail.com>
 *
 * @copyright Copyright (c) 2025 Mohamed-Ismail MEJRI
 *
 * @license GNU AGPL version 3 or any later version
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as
 * published by the Free Software Foundation, either version 3 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 */

namespace OCA\NCGrisbi\Tools;

class Helper {
	public const APP_ID = 'ncgrisbi';

	public static function findBinaryPath($program, $default = null) {
		$memcache = \OC::$server->getMemCacheFactory()->createDistributed('findBinaryPath');
		if ($memcache->hasKey($program)) {
			return $memcache->get($program);
		}

		$dataPath = \OC::$server->getSystemConfig()->getValue('datadirectory');
		$paths = ['/usr/local/sbin', '/usr/local/bin', '/usr/sbin', '/usr/bin', '/sbin', '/bin', '/opt/bin', $dataPath . "/bin"];
		$result = $default;
		$exeSniffer = new ExecutableFinder();
		// Returns null if nothing is found
		$result = $exeSniffer->find($program, $default, $paths);
		if ($result) {
			// store the value for 5 minutes
			$memcache->set($program, $result, 300);
		}
		return $result;
	}

	public static function pythonInstalled(): bool {
		return (self::findBinaryPath('python') || self::findBinaryPath('python3'));
	}

	public static function getAppPath(): string {
		return \OC::$server->getAppManager()->getAppPath(self::APP_ID);
	}

	public static function getVersion(): string {
		return \OC::$server->getAppManager()->getAppVersion(self::APP_ID);
	}
}
