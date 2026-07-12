<?php
declare(strict_types=1);

function phase5_check(bool $condition, string $message): void {
    if (!$condition) {
        fwrite(STDERR, $message . PHP_EOL);
        exit(1);
    }
}

$root = dirname(__DIR__, 2);
$routes = file_get_contents($root . '/appinfo/routes.php');
$controller = file_get_contents($root . '/lib/Controller/EditorController.php');
$service = file_get_contents($root . '/lib/Service/GsbDocumentService.php');
$view = file_get_contents($root . '/src/views/TransactionListView.vue');
$api = file_get_contents($root . '/src/services/gsbApi.js');
$entrypoint = file_get_contents($root . '/lib/bin/ncgrisbi_protocol.py');

phase5_check(str_contains($routes, "'/api/editor/account/{accountId}'"), 'editor snapshot route is missing');
$accountPosition = strpos($controller, 'public function account(');
phase5_check($accountPosition !== false, 'editor account controller is missing');
$attributes = substr($controller, max(0, $accountPosition - 220), 220);
phase5_check(!str_contains($attributes, 'NoCSRFRequired'), 'editor snapshot bypasses CSRF');
phase5_check(str_contains($service, 'LOCK_SHARED'), 'snapshot does not use the application shared lock');
phase5_check(str_contains($service, 'getAccountSnapshot('), 'snapshot service is missing');
phase5_check(str_contains($api, "@nextcloud/axios"), 'frontend does not use Nextcloud axios');
phase5_check(str_contains($api, 'baseEtag'), 'frontend mutation API does not send baseEtag');
phase5_check(!str_contains($view, '/api/savetransaction'), 'frontend still calls the disabled legacy writer');
phase5_check(!str_contains($view, "'Trt'"), 'frontend still constructs raw transfer attributes');
phase5_check(!str_contains($view, "'Ac'"), 'frontend still constructs raw GSB transactions');
phase5_check(str_contains($view, 'etag-conflict'), 'frontend does not handle ETag conflicts');
phase5_check(str_contains($view, 'row.protected'), 'frontend does not protect transfer/split rows');
phase5_check(str_contains($entrypoint, 'phase5_protocol'), 'worker entrypoint does not use Phase 5 protocol');

echo "phase5 source contract tests passed\n";
