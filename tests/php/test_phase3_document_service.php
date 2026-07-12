<?php
declare(strict_types=1);

namespace OCP\Files {
    class NotFoundException extends \RuntimeException {}
    interface File {
        public function getContent();
        public function putContent($data);
        public function getId();
        public function getEtag();
        public function getSize($includeMounts = true);
        public function lock($type);
        public function unlock($type);
    }
    interface Folder {
        public function get($path);
    }
    interface IRootFolder {
        public function getUserFolder($userId);
    }
}
namespace OCP\Lock {
    interface ILockingProvider {
        public const LOCK_EXCLUSIVE = 2;
    }
}
namespace Phase3Test {
    use OCP\Files\File;
    use OCP\Files\Folder;
    use OCP\Files\IRootFolder;

    final class FakeFile implements File {
        public int $writes = 0;
        public bool $locked = false;

        public function __construct(
            public string $content,
            public string $etag = 'etag-1'
        ) {
        }

        public function getContent() {
            return $this->content;
        }

        public function putContent($data) {
            $this->content = (string)$data;
            $this->writes++;
            $this->etag = 'etag-' . ($this->writes + 1);
        }

        public function getId() {
            return 42;
        }

        public function getEtag() {
            return $this->etag;
        }

        public function getSize($includeMounts = true) {
            return strlen($this->content);
        }

        public function lock($type) {
            if ($this->locked) {
                throw new \RuntimeException('double lock');
            }
            $this->locked = true;
        }

        public function unlock($type) {
            $this->locked = false;
        }
    }

    final class FakeFolder implements Folder {
        public function __construct(private FakeFile $file) {
        }

        public function get($path) {
            return $this->file;
        }
    }

    final class FakeRoot implements IRootFolder {
        public function __construct(private FakeFolder $folder) {
        }

        public function getUserFolder($userId) {
            return $this->folder;
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
    use Phase3Test\FakeFile;
    use Phase3Test\FakeFolder;
    use Phase3Test\FakeRoot;

    function check_service(bool $condition, string $message): void {
        if (!$condition) {
            fwrite(STDERR, $message . PHP_EOL);
            exit(1);
        }
    }

    $file = new FakeFile('GSB');
    $process = GrisbiProcess::createForTesting(
        'python3',
        __DIR__ . '/fake_protocol_worker.py',
        __DIR__ . '/fake_protocol_worker.py'
    );
    $service = new GsbDocumentService(
        new FakeRoot(new FakeFolder($file)),
        'user',
        $process
    );

    $state = $service->getState('/Documents/test.gsb');
    check_service($state['etag'] === 'etag-1', 'state etag is incorrect');
    check_service($state['encrypted'] === false, 'plain file marked encrypted');

    $result = $service->mutate(
        'Documents/test.gsb',
        'etag-1',
        [['type' => 'deleteTransaction', 'transactionId' => '10']],
        's ecret'
    );
    check_service($result['changed'] === true, 'mutation should be changed');
    check_service($file->content === 'GSB!', 'service did not write protocol output');
    check_service($file->writes === 1, 'service must perform exactly one write');
    check_service($file->locked === false, 'service did not release the lock');
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
        check_service(
            $e->getCurrentEtag() === 'etag-2',
            'conflict etag is incorrect'
        );
    }
    check_service($file->writes === 1, 'conflict request wrote the file');
    check_service($file->locked === false, 'conflict did not release the lock');

    echo "phase3 document service tests passed\n";
}
