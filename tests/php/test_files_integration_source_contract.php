<?php
declare(strict_types=1);

$root = dirname(__DIR__, 2);

function files_contract(bool $valid, string $reason): void {
    if (!$valid) {
        fwrite(STDERR, $reason . PHP_EOL);
        exit(1);
    }
}

$info = file_get_contents($root . '/appinfo/info.xml');
$app = file_get_contents($root . '/lib/AppInfo/Application.php');
$listener = file_get_contents($root . '/lib/Listener/LoadAdditionalListener.php');
$template = file_get_contents($root . '/templates/main.php');
$viewer = file_get_contents($root . '/src/viewer.js');
$recognition = file_get_contents($root . '/src/domain/gsbFileRecognition.mjs');

files_contract(
    str_contains($info, 'min-version="33"') && str_contains($info, 'max-version="35"'),
    'NCGrisbi must target the Files API supported by Nextcloud 33–35'
);
files_contract(
    str_contains($app, 'registerEventListener(')
    && str_contains($app, 'LoadAdditionalScriptsEvent::class')
    && str_contains($app, 'LoadAdditionalListener::class'),
    'Files initialization listener is not registered'
);
files_contract(
    str_contains($listener, "Util::addInitScript(Application::APP_ID, 'viewer')"),
    'Viewer action must load before the Files app initializes'
);
files_contract(
    !str_contains($app, 'Util::addScript(')
    && !str_contains($template, "script('ncgrisbi', 'viewer')"),
    'Viewer action must not load globally or twice'
);
files_contract(
    str_contains($viewer, 'registerFileAction(fileAction)')
    && str_contains($viewer, 'FileType.File')
    && str_contains($viewer, 'Permission.READ')
    && str_contains($viewer, 'nodes.length === 1'),
    'Modern single-file action guard is missing'
);
files_contract(
    str_contains($recognition, '/\\.gsb$/i.test(node.path)')
    && !str_contains($recognition, 'node.mime'),
    'GSB action must work with stale MIME caches and reject other extensions'
);
files_contract(
    str_contains($viewer, "generateUrl('/apps/ncgrisbi/file')")
    && str_contains($viewer, 'encodeURIComponent(nodes[0].path)'),
    'File opening URL must preserve the exact path'
);

echo "Files integration source contract tests passed\n";
