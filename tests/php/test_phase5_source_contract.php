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
$process = file_get_contents($root . '/lib/Grisbi/GrisbiProcess.php');
$view = file_get_contents($root . '/src/views/TransactionListView.vue');
$api = file_get_contents($root . '/src/services/gsbApi.js');
$wire = file_get_contents($root . '/src/domain/snapshotWire.mjs');
$editor = file_get_contents($root . '/src/domain/transactionEditor.mjs');
$entrypoint = file_get_contents($root . '/lib/bin/ncgrisbi_protocol.py');
$worker = file_get_contents($root . '/lib/bin/ncgrisbi/worker.py');
$mutation = file_get_contents($root . '/lib/bin/ncgrisbi/mutation.py');
$mutationCore = file_get_contents($root . '/lib/bin/ncgrisbi/_mutation_core.py');
$snapshot = file_get_contents($root . '/lib/bin/ncgrisbi/snapshot.py');
$snapshotCore = file_get_contents($root . '/lib/bin/ncgrisbi/_snapshot_core.py');
$validator = file_get_contents($root . '/lib/bin/ncgrisbi/validator.py');
$writer = file_get_contents($root . '/lib/bin/ncgrisbi/writer.py');
$formatRegistry = file_get_contents($root . '/lib/bin/ncgrisbi/formats/__init__.py');
$format121 = file_get_contents($root . '/lib/bin/ncgrisbi/formats/gsb_121.py');

phase5_check(
    str_contains($routes, "'/api/editor/account/{accountId}'"),
    'editor snapshot route is missing'
);
$accountPosition = strpos($controller, 'public function account(');
phase5_check($accountPosition !== false, 'editor controller is missing');
phase5_check(
    !str_contains(substr($controller, max(0, $accountPosition - 220), 220), 'NoCSRFRequired'),
    'editor snapshot bypasses CSRF'
);
phase5_check(str_contains($service, 'LOCK_SHARED'), 'snapshot does not use shared lock');
phase5_check(
    str_contains($api, '@nextcloud/axios') && str_contains($api, 'baseEtag'),
    'Nextcloud axios or ETag contract is missing'
);
phase5_check(str_contains($wire, 'wire.v !== 2'), 'compact snapshot decoder is missing');
phase5_check(str_contains($wire, 'linesPerTransaction'), 'Grisbi display preferences are not decoded');
phase5_check(str_contains($snapshotCore, '"U": preferences'), 'display preferences are not encoded');
phase5_check(str_contains($snapshotCore, '"W": warnings'), 'compatibility warnings are not encoded');
phase5_check(str_contains($snapshot, 'prefer_current_account_history'), 'completion precedence is outside the canonical snapshot module');
phase5_check(str_contains($view, 'DynamicScroller'), 'large transaction lists are not virtualized');
phase5_check(str_contains($view, 'TRANSFER_CATEGORY'), 'transfer selection is missing');

phase5_check(str_contains($entrypoint, 'ncgrisbi.worker'), 'active script does not run the consolidated worker');
phase5_check(
    str_contains($worker, 'from .mutation import apply_mutations')
    && !str_contains($worker, 'for operation_index, raw in enumerate'),
    'worker does not use the one-pass mutation API'
);
phase5_check(
    str_contains($mutation, 'class MutationSession')
    && str_contains($mutation, 'format_profile')
    && str_contains($mutation, 'apply_mutations'),
    'canonical mutation module is incomplete'
);
phase5_check(str_contains($mutationCore, 'setTransactionMarks'), 'quick mark mutation is missing');
phase5_check(str_contains($mutationCore, 'convertTransactionToTransfer'), 'normal-to-transfer conversion is missing');
phase5_check(str_contains($mutationCore, 'convertTransferToTransaction'), 'transfer-to-normal conversion is missing');
phase5_check(str_contains($mutationCore, 'allowReconciled'), 'reconciled transfer confirmation is missing');
phase5_check(str_contains($writer, 'self.profile.serialize_record'), 'writer bypasses the format profile');
phase5_check(str_contains($writer, 'replace_attribute'), 'attribute-level Ma patching is missing');
phase5_check(str_contains($formatRegistry, 'GSB_121_PROFILE'), 'format registry is missing the 1.2.1 profile');
phase5_check(str_contains($format121, 'file_version="1.2.1"'), '1.2.1 format profile is missing');
phase5_check(str_contains($validator, 'profile.attribute_order.items()'), 'validator bypasses the format profile');
phase5_check(str_contains($editor, "type: 'setTransactionMarks'"), 'frontend does not batch quick marks');
phase5_check(
    str_contains($view, 'row.isNew || row.quickMarkable')
    && str_contains($view, 'quickMarkChanged')
    && !str_contains($view, ':disabled="!isEditable(row)" @change="row.marked'),
    'marked checkbox still requires full edit mode'
);
phase5_check(
    str_contains($validator, '_collect_unique(root, "Payment", "Number"'),
    'payment IDs are not validated globally like Grisbi'
);
phase5_check(str_contains($validator, 'severity="warning"'), 'damaged transfer links remain fatal');
phase5_check(!str_contains($view, '/api/savetransaction'), 'frontend still calls legacy writer');
phase5_check(
    !str_contains($view, "'Trt'") && !str_contains($view, "'Ac'"),
    'frontend constructs raw GSB attributes'
);
phase5_check(str_contains($view, 'etag-conflict'), 'ETag conflicts are not handled');
phase5_check(str_contains($process, "'command' => 'listAccounts'"), 'account reads do not use the framed worker');
phase5_check(!str_contains($process, '$this->legacyWrapperPath'), 'PHP still has an executable legacy CLI path');

$removed = [
    'compat_engine.py',
    'completion_history.py',
    'index.py',
    'mutation_engine.py',
    'mutations.py',
    'phase4_protocol.py',
    'phase5_protocol.py',
    'phase6_engine.py',
    'protocol.py',
    'read_service.py',
    'resolution.py',
    'serializer_121.py',
    'snapshot_service.py',
];
foreach ($removed as $file) {
    phase5_check(
        !file_exists($root . '/lib/bin/ncgrisbi/' . $file),
        'obsolete backend module remains: ' . $file
    );
}


echo "target backend source contract tests passed\n";
