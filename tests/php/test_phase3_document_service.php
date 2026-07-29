<?php
declare(strict_types=1);

namespace OCP {
    interface IUser { public function getUID(); }
    interface IUserSession { public function getUser(); }
}
namespace OCP\Files {
    class NotFoundException extends \RuntimeException {}
    interface File {
        public function getContent();
        public function putContent($data);
        public function getId();
        public function getEtag();
        public function getSize($includeMounts = true);
    }
    interface Folder { public function get($path); }
    interface IRootFolder { public function getUserFolder($userId); }
}
namespace OCP\Lock {
    interface ILockingProvider {
        public const LOCK_SHARED = 1;
        public const LOCK_EXCLUSIVE = 2;
        public function acquireLock(string $path, int $type, ?string $readablePath = null): void;
        public function releaseLock(string $path, int $type): void;
    }
}
namespace Phase3Test {
    use OCP\Files\File;
    use OCP\Files\Folder;
    use OCP\Files\IRootFolder;
    use OCP\IUser;
    use OCP\IUserSession;
    use OCP\Lock\ILockingProvider;

    final class FakeUser implements IUser { public function getUID() { return 'user'; } }
    final class FakeUserSession implements IUserSession { public function getUser() { return new FakeUser(); } }
    final class FakeFile implements File {
        public int $writes = 0;
        public function __construct(public string $content, public string $etag = 'etag-1') {}
        public function getContent() { return $this->content; }
        public function putContent($data) {
            $this->content = (string)$data;
            $this->writes++;
            $this->etag = 'etag-' . ($this->writes + 1);
        }
        public function getId() { return 42; }
        public function getEtag() { return $this->etag; }
        public function getSize($includeMounts = true) { return strlen($this->content); }
    }
    final class FakeFolder implements Folder {
        public function __construct(private FakeFile $file) {}
        public function get($path) { return $this->file; }
    }
    final class FakeRoot implements IRootFolder {
        public function __construct(private FakeFolder $folder) {}
        public function getUserFolder($userId) { return $this->folder; }
    }
    final class FakeLockingProvider implements ILockingProvider {
        public bool $locked = false;
        public ?string $lastKey = null;
        public ?int $lastAcquireType = null;
        public function acquireLock(string $path, int $type, ?string $readablePath = null): void {
            if ($this->locked) { throw new \RuntimeException('double lock'); }
            $this->locked = true;
            $this->lastKey = $path;
            $this->lastAcquireType = $type;
        }
        public function releaseLock(string $path, int $type): void {
            if ($path !== $this->lastKey || $type !== $this->lastAcquireType) {
                throw new \RuntimeException('wrong lock release');
            }
            $this->locked = false;
        }
    }
}
namespace {
    require __DIR__ . '/../../lib/Grisbi/ProtocolFrame.php';
    require __DIR__ . '/../../lib/Exception/GrisbiProtocolException.php';
    require __DIR__ . '/../../lib/Exception/DocumentConflictException.php';
    require __DIR__ . '/../../lib/Exception/DocumentNotFoundException.php';
    require __DIR__ . '/../../lib/Grisbi/GrisbiProcess.php';
    require __DIR__ . '/../../lib/Service/GsbDocumentService.php';

    use OCA\NCGrisbi\Exception\DocumentConflictException;
    use OCA\NCGrisbi\Grisbi\GrisbiProcess;
    use OCA\NCGrisbi\Service\GsbDocumentService;
    use OCP\Lock\ILockingProvider;
    use Phase3Test\FakeFile;
    use Phase3Test\FakeFolder;
    use Phase3Test\FakeLockingProvider;
    use Phase3Test\FakeRoot;
    use Phase3Test\FakeUserSession;

    function check_service(bool $condition, string $message): void {
        if (!$condition) { fwrite(STDERR, $message . PHP_EOL); exit(1); }
    }

    $file = new FakeFile('GSB');
    $locks = new FakeLockingProvider();
    $process = GrisbiProcess::createForTesting(
        'python3',
        __DIR__ . '/fake_protocol_worker.py',
        __DIR__ . '/fake_protocol_worker.py'
    );
    $service = new GsbDocumentService(
        new FakeRoot(new FakeFolder($file)),
        new FakeUserSession(),
        $process,
        $locks
    );

    $state = $service->getState('/Documents/test.gsb');
    check_service($state['etag'] === 'etag-1', 'state etag is incorrect');

    $snapshot = $service->getAccountSnapshot(
        'Documents/test.gsb',
        '1',
        's ecret'
    );
    check_service($snapshot['document']['etag'] === 'etag-1', 'snapshot etag is incorrect');
    check_service($snapshot['snapshot']['account']['id'] === '1', 'snapshot account is incorrect');
    check_service($file->writes === 0, 'snapshot wrote the file');
    check_service($locks->lastAcquireType === ILockingProvider::LOCK_SHARED, 'snapshot did not use shared lock');
    check_service($locks->locked === false, 'snapshot did not release shared lock');

    $result = $service->mutate(
        'Documents/test.gsb',
        'etag-1',
        [['type' => 'deleteTransaction', 'transactionId' => '10']],
        's ecret'
    );
    check_service($result['changed'] === true, 'mutation should be changed');
    check_service($file->content === 'GSB!', 'service did not write protocol output');
    check_service($file->writes === 1, 'service must perform exactly one write');
    check_service($locks->lastAcquireType === ILockingProvider::LOCK_EXCLUSIVE, 'mutation did not use exclusive lock');
    check_service($locks->locked === false, 'service did not release the lock');
    check_service($result['etag'] === 'etag-2', 'new etag was not returned');

    try {
        $service->mutate(
            'Documents/test.gsb',
            'stale-etag',
            [['type' => 'deleteTransaction', 'transactionId' => '10']],
            's ecret'
        );
        check_service(false, 'stale etag was accepted');
    } catch (DocumentConflictException $e) {
        check_service($e->getCurrentEtag() === 'etag-2', 'conflict etag is incorrect');
    }
    check_service($file->writes === 1, 'conflict request wrote the file');
    check_service($locks->locked === false, 'conflict did not release the lock');

    echo "phase3/phase5 document service tests passed\n";
}
