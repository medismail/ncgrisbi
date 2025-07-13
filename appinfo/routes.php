<?php
declare(strict_types=1);

return [
    'routes' => [
        // Vue app page
        ['name' => 'page#index', 'url' => '/', 'verb' => 'GET'],
        ['name' => 'page#accounts', 'url' => '/accounts', 'verb' => 'GET'],
        ['name' => 'page#file', 'url' => '/file', 'verb' => 'GET'],

        // API endpoints
        ['name' => 'api#get_accounts', 'url' => '/api/accounts', 'verb' => 'POST'],
        ['name' => 'api#get_transactions', 'url' => '/api/account/{accountId}', 'verb' => 'POST'],
        ['name' => 'api#save_transaction', 'url' => '/api/savetransaction', 'verb' => 'POST'],
        ['name' => 'api#get_parties', 'url' => '/api/parties', 'verb' => 'POST'],
        ['name' => 'api#check_encrypted', 'url' => '/api/checkencrypted', 'verb' => 'GET'],
    ]
];
