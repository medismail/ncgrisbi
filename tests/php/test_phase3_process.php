<?php
declare(strict_types=1);

require __DIR__ . '/../../lib/Grisbi/ProtocolFrame.php';
require __DIR__ . '/../../lib/Exception/GrisbiProtocolException.php';
require __DIR__ . '/../../lib/Grisbi/GrisbiProcess.php';

use OCA\NCGrisbi\Grisbi\GrisbiProcess;
use OCA\NCGrisbi\Grisbi\ProtocolFrame;

function check(bool $condition, string $message): void {
    if (!$condition) {
        fwrite(STDERR, $message . PHP_EOL);
        exit(1);
    }
}

$binary = "\x00gsb\xff";
$frame = ProtocolFrame::encode(['version' => 1, 'command' => 'mutate'], $binary);
[$header, $payload] = ProtocolFrame::decode($frame);
check($header['payloadLength'] === strlen($binary), 'payload length was not encoded');
check($payload === $binary, 'binary frame was not preserved');

$worker = __DIR__ . '/fake_protocol_worker.py';
$process = GrisbiProcess::createForTesting('python3', $worker, $worker);
$process->setPassword('s ecret');
$result = $process->mutate(
    [['type' => 'deleteTransaction', 'transactionId' => '10']],
    'GSB'
);
check($result['content'] === 'GSB!', 'protocol payload did not round trip');
check($result['changed'] === true, 'changed flag was not returned');
check($result['outcomes'][0]['recordId'] === '13', 'outcome was not returned');

echo "phase3 php process tests passed\n";
