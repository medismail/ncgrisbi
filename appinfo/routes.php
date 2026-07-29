<?php
declare(strict_types=1);

return [
    'routes' => [
        // Vue app page
        ['name' => 'page#index', 'url' => '/', 'verb' => 'GET'],
        ['name' => 'page#accounts', 'url' => '/accounts', 'verb' => 'GET'],
        ['name' => 'page#account', 'url' => '/account/{id}', 'verb' => 'GET'],
        ['name' => 'page#typepass', 'url' => '/typepass', 'verb' => 'GET'],
        ['name' => 'page#file', 'url' => '/file', 'verb' => 'GET'],

        // Legacy read-only API endpoints
        ['name' => 'api#get_accounts', 'url' => '/api/accounts', 'verb' => 'POST'],
        ['name' => 'api#get_transactions', 'url' => '/api/account/{accountId}', 'verb' => 'POST'],
        ['name' => 'api#get_parties', 'url' => '/api/parties', 'verb' => 'POST'],
        ['name' => 'api#get_categories', 'url' => '/api/categories', 'verb' => 'POST'],
        ['name' => 'api#check_encrypted', 'url' => '/api/checkencrypted', 'verb' => 'GET'],

        // Typed editor snapshot and concurrency-safe mutation API
        ['name' => 'editor#account', 'url' => '/api/editor/account/{accountId}', 'verb' => 'POST'],
        ['name' => 'api#document_state', 'url' => '/api/document', 'verb' => 'POST'],
        ['name' => 'api#mutate', 'url' => '/api/mutations', 'verb' => 'POST'],

        // Retained only to return HTTP 410 to pre-Phase-3 clients.
        ['name' => 'api#save_transaction', 'url' => '/api/savetransaction', 'verb' => 'POST'],
    ],
];
