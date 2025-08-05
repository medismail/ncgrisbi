<?php
declare(strict_types=1);

namespace OCA\NCGrisbi\Controller;

use OCP\AppFramework\Controller;
use OCP\AppFramework\Http\TemplateResponse;
use OCP\AppFramework\Http\RedirectResponse;
use OCP\Appframework\Http\Attribute\NoCSRFRequired;
use OCP\AppFramework\Http\Attribute\NoAdminRequired;
use OCP\IRequest;
use OCP\IURLGenerator;

class PageController extends Controller {

    private $urlGenerator;

    public function __construct(
        $appName,
        IURLGenerator $urlGenerator,
        IRequest $request
    ) {
        parent::__construct($appName, $request);
        $this->urlGenerator = $urlGenerator;
    }

    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function index(): TemplateResponse {
        return new TemplateResponse('ncgrisbi', 'main');
    }

    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function accounts($file): TemplateResponse | RedirectResponse {
        $response = null;
        if (isset($file)) {
            $response = new TemplateResponse('ncgrisbi', 'main');
        } else {
            $response = new RedirectResponse($this->urlGenerator->linkToRoute('ncgrisbi.page.index'));
        }
        return $response;

    }

    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function account($id, $file): TemplateResponse | RedirectResponse {
        $response = null;
        if (isset($file)) {
            $response = new TemplateResponse('ncgrisbi', 'main');
        } else {
            $response = new RedirectResponse($this->urlGenerator->linkToRoute('ncgrisbi.page.index'));
        }
        return $response;

    }

    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function typepass($file): TemplateResponse | RedirectResponse {
        $response = null;
        if (isset($file)) {
            $response = new TemplateResponse('ncgrisbi', 'main');
        } else {
            $response = new RedirectResponse($this->urlGenerator->linkToRoute('ncgrisbi.page.index'));
        }
        return $response;

    }

    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function file($open): RedirectResponse {
        $response = null;
        if (isset($open)) {
            $response = new RedirectResponse($this->urlGenerator->linkToRoute('ncgrisbi.page.accounts').'?file='.urlencode($open));
        } else {
            $response = new RedirectResponse($this->urlGenerator->linkToRoute('ncgrisbi.page.index').'accounts?file='.urlencode($open));
        }
        return $response;
    }
}
