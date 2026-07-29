<?php
declare(strict_types=1);

function contract_check(bool $condition, string $message): void {
    if (!$condition) {
        fwrite(STDERR, $message . PHP_EOL);
        exit(1);
    }
}

$root = dirname(__DIR__, 2);
$controller = file_get_contents($root . '/lib/Controller/ApiController.php');
$process = file_get_contents($root . '/lib/Grisbi/GrisbiProcess.php');
$routes = file_get_contents($root . '/appinfo/routes.php');
$service = file_get_contents($root . '/lib/Service/GsbDocumentService.php');

contract_check(
    str_contains($routes, "'/api/mutations'"),
    'mutation route is missing'
);
contract_check(
    str_contains($routes, "'/api/document'"),
    'document route is missing'
);
contract_check(
    str_contains($controller, '], 410);'),
    'legacy writer is not disabled'
);

$mutatePosition = strpos($controller, 'public function mutate(');
contract_check($mutatePosition !== false, 'mutation controller is missing');
$mutateAttributes = substr(
    $controller,
    max(0, $mutatePosition - 180),
    180
);
contract_check(
    !str_contains($mutateAttributes, 'NoCSRFRequired'),
    'mutation endpoint bypasses CSRF'
);

$legacyPosition = strpos($controller, 'public function saveTransaction(');
contract_check($legacyPosition !== false, 'legacy endpoint is missing');
$legacyAttributes = substr(
    $controller,
    max(0, $legacyPosition - 180),
    180
);
contract_check(
    !str_contains($legacyAttributes, 'NoCSRFRequired'),
    'legacy write endpoint bypasses CSRF'
);
contract_check(
    !str_contains($process, "'--pass-word'"),
    'PHP still places password on command line'
);
contract_check(
    str_contains($process, "3 => ['pipe', 'r']"),
    'password descriptor is missing'
);
contract_check(
    str_contains($service, 'acquireLock('),
    'application mutation lock is missing'
);
contract_check(
    !str_contains($service, '$file->lock('),
    'service recursively locks the file before putContent'
);
contract_check(
    str_contains($service, 'IUserSession'),
    'service does not resolve the authenticated user through IUserSession'
);

echo "phase3 source contract tests passed\n";
