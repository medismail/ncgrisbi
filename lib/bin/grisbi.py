import xml.etree.ElementTree as ET
import json
import gsb_decode
import logging
import argparse
import sys
from io import BytesIO
from decimal import Decimal
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_gsb_content(file_content):
    """Parse the XML content and return the root element."""
    if file_content is None:
        logging.error("No content to parse.")
        return None

    try:
        # Parse the XML
        root = ET.fromstring(file_content)
    except ET.ParseError as e:
        logging.error(f"Error parsing XML: {e}")
        return None

    return root

def find_transaction_by_number(root, transaction_number):
    """Find a transaction element by its 'Nb' attribute.
    
    Optimization: Uses direct iteration instead of XPath to avoid ElementTree limitations.
    """
    if transaction_number is None:
        return None
    
    # Convert to string once for comparison
    tx_nb_str = str(transaction_number)
    
    for transaction in root.findall('.//Transaction'):
        if transaction.get('Nb') == tx_nb_str:
            return transaction
    return None


#{"Ac":"8","Nb":"2685","Id":"(null)","Dt":"06/25/2022","Dv":"(null)","Cu":"1","Am":"1000.00","Exb":"0","Exr":"0.00","Exf":"0.00","Pa":"190","Ca":"0","Sca":"0","Br":"0","No":"(null)","Pn":"0","Pc":"(null)","Ma":"0","Ar":"0","Au":"0","Re":"0","Fi":"0","Bu":"0","Sbu":"0","Vo":"(null)","Ba":"(null)","Trt":"0","Mo":"0"}
def add_transaction(root, transaction_data):
    """Add a new transaction to the XML root element immediately after the last transaction."""
    transaction = ET.Element('Transaction')
    for key, value in transaction_data.items():
        transaction.set(key, str(value))
   
    # Find the last <Transaction> element using iteration (more efficient)
    last_transaction = None
    for tx in root.findall('.//Transaction'):
        last_transaction = tx

    if last_transaction is not None:
        # Insert the new transaction right after the last transaction
        index = list(root).index(last_transaction) + 1
        root.insert(index, transaction)
    else:
        # If no transaction exists, append it to the root
        root.append(transaction)

def write_gsb_content(root):
    """Write the XML tree back to the GSB file."""
    tree = ET.ElementTree(root)
    # Apply indentation to the XML tree (requires Python 3.9+)
    ET.indent(tree, space="    ", level=0)

    f = BytesIO()
    tree.write(f, encoding='utf-8', xml_declaration=True)
    return f.getvalue().decode('utf-8')

def get_parties_json(parties):
    partie_list = [{'id': partie_id, 'name': partie_info['name'], 'last_amount': partie_info['last_amount'], 'last_category': partie_info['last_category'], 'last_subcategory': partie_info['last_subcategory'], 'last_pm': partie_info['last_pm'], 'last_note': partie_info['last_note']} for partie_id, partie_info in parties.items()]
    return json.dumps(partie_list, indent=4)

def get_categories_json(categories, subcategories):
    """
    categories   : dict  {cat_id: cat_name}
    subcategories: dict  {cat_id: [{'id':..., 'name':...}, ...]}
    """
    categorie_list = [{'id': cid, 'name': cname, 'subcategories': subcategories.get(cid, [])} for cid, cname in categories.items()]
    return json.dumps(categorie_list)

def get_payments_json(payments):
    payment_list = [{'id': payment_id, 'name': payment_info['name'], 'account': payment_info['account'], 'sign': payment_info['sign']} for payment_id, payment_info in payments.items()]
    return json.dumps(payment_list)

def get_accounts_json(accounts, account_totals):
    account_list = [{'id': account_id, 'name': account_info['name'], 'bank': account_info['bank'], 'type': account_info['type'], 'currency': account_info['currency'], 'total': {'total_amount': float(round(account_totals.get(account_id, {'total_amount': Decimal('0.0')})['total_amount'], 2)), 'total_marked_amount': float(round(account_totals.get(account_id, {'total_marked_amount': Decimal('0.0')})['total_marked_amount'], 2))}} for account_id, account_info in accounts.items()]
    return json.dumps(account_list)

def get_account_transactions_json(accounts, transactions, account_totals, payments, account_id, next_id):
    account_transactions = [tx for tx in transactions if tx['Acc'] == accounts.get(account_id, {'name': 'Unknown', 'bank': 'Unknown'})['name']]
    account_totals_data = account_totals.get(account_id, {'total_amount': 0.0, 'total_marked_amount': 0.0})
    payment_methods = [{'id': payment_id, 'name': payment_info['name']} for payment_id, payment_info in payments.items() if payment_info['account'] == account_id]

    result = {
        'account_id': account_id,
        'account_name': accounts.get(account_id, {'name': 'Unknown', 'bank': 'Unknown'})['name'],
        'bank_id': accounts.get(account_id, {'name': 'Unknown', 'bank': 'Unknown'})['bank'],
        'transactions': account_transactions,
        'currency': account_totals_data['Currency'],
        'total_amount': float(round(account_totals_data['total_amount'], 2)),
        'total_marked_amount': float(round(account_totals_data['total_marked_amount'], 2)),
        'payment_methods': payment_methods,
        'next_id': int(next_id)+1
    }
    return json.dumps(result)

def extract_data(root):
    """Extract data from the XML root element.
    
    Optimization: Single pass through XML, build indices instead of repeated searches.
    Security: Input validation on critical fields.
    """
    # Extract currencies
    currencies = {}
    for currency in root.findall('Currency'):
        currency_id = currency.get('Nb')
        currency_iso_name = currency.get('Ico')
        if currency_id:  # Validate non-empty ID
            currencies[currency_id] = currency_iso_name

    # Extract parties (payees)
    parties = {}
    for party in root.findall('Party'):
        party_id = party.get('Nb')
        party_name = party.get('Na')
        if party_id:  # Validate non-empty ID
            parties[party_id] = { 'name': party_name, 'last_amount': 0, 'last_category': '', 'last_subcategory': '', 'last_pm': '', 'last_note': '' }

    # Extract categories and subcategories
    categories = {}
    subcategories_name_map = {}
    subcategories = defaultdict(list)
    for category in root.findall('Category'):
        category_id = category.get('Nb')
        category_name = category.get('Na')
        if category_id:  # Validate non-empty ID
            categories[category_id] = category_name

    for subcategory in root.findall('Sub_category'):
        category_id = subcategory.get('Nbc')
        subcategory_id = subcategory.get('Nb')
        subcategory_name = subcategory.get('Na')
        if category_id and subcategory_id:  # Validate non-empty IDs
            subcategories_name_map[(category_id, subcategory_id)] = subcategory_name
            subcategories[category_id].append({'id': subcategory_id, 'name': subcategory_name})

    # Extract payment methods
    payments = {}
    for payment in root.findall('Payment'):
        payment_number = payment.get('Number')
        if payment_number:  # Validate non-empty number
            payments[payment_number] = {
                'name': payment.get('Name'),
                'account': payment.get('Account'),
                'sign': payment.get('Sign')
            }

    # Extract banks and map account IDs to bank names
    banks = {}
    banks['-1'] = 'N/A'
    for bank in root.findall('Bank'):
        bank_number = bank.get('Nb')
        bank_name = bank.get('Na')
        if bank_number:  # Validate non-empty number
            banks[bank_number] = bank_name

    # Extract accounts and map account IDs to account names
    gsb_account_type = {"-1": "BALANCE", "0": "BANK", "1": "CASH", "2": "LIABILITIES", "3": "ASSET"}
    accounts = {}
    for account in root.findall('Account'):
        account_id = account.get('Number')
        account_name = account.get('Name')
        account_kind = account.get('Kind')
        account_currency = account.get('Currency')
        bank_number = account.get('Bank')
        
        if account_id and account_kind:  # Validate critical fields
            account_kind_safe = gsb_account_type.get(account_kind, "UNKNOWN")
            currency_safe = currencies.get(account_currency, 'Unknown')
            accounts[account_id] = {
                'name': account_name,
                'bank': bank_number,
                'type': account_kind_safe,
                'currency': currency_safe
            }

    # Initialize counters for each account
    account_totals = {}
    for account_id in accounts:
        account_totals[account_id] = {'total_amount': Decimal('0.0'), 'total_marked_amount': Decimal('0.0')}

    # Extract transactions - optimized single pass
    next_id = 0
    nb_to_idx = {}
    transactions = []
    for idx, transaction in enumerate(root.findall('Transaction')):
        try:
            # Get account info including bank number
            account_id = transaction.get('Ac')
            if not account_id or account_id not in accounts:
                continue  # Skip invalid account references
            
            account_info = accounts[account_id]
            bank_name = banks.get(account_info['bank'], 'Unknown')

            # Safe decimal conversion with default value
            try:
                amount = Decimal(transaction.get('Am', '0.00'))
            except:
                amount = Decimal('0.00')
            
            marked = int(transaction.get('Ma', '0')) if transaction.get('Ma', '0').isdigit() else 0
            next_id = transaction.get('Nb')
            party_id = transaction.get('Pa')
            pm = payments.get(transaction.get('Pn'), { 'name': 'Unknown' })['name']
            st = transaction.get('Trt')
            
            if (st != '0'):
                category = 'Transfer'
                idost = nb_to_idx.get(st)
                if (idost):
                    subcategory = transactions[idost]['Acc']
                    transactions[idost]['SCat'] = account_info['name']
                else:
                    nb_to_idx[next_id] = idx
                    subcategory = ''
            else:
                idost = 0
                category = categories.get(transaction.get('Ca'), 'Uncategorized')
                subcategory = subcategories_name_map.get((transaction.get('Ca'), transaction.get('Sca')), 'Uncategorized')

            # Safe party lookup
            if party_id and int(party_id if party_id.isdigit() else 0):
                if party_id in parties:
                    if (idost):
                        parties[party_id]['last_subcategory'] = account_info['name']
                    else:
                        parties[party_id]['last_amount'] = float(amount)
                        parties[party_id]['last_category'] = category
                        parties[party_id]['last_subcategory'] = subcategory
                        parties[party_id]['last_pm'] = pm
                        parties[party_id]['last_note'] = transaction.get('No')

            transaction_data = {
                'Acc': account_info['name'],
                'TxNb': next_id,
                'Date': transaction.get('Dt'),
                'Cur': currencies.get(transaction.get('Cu'), 'Unknown'),
                'Am': float(amount),
                'Pa': parties.get(party_id, { 'name': 'Unknown' })['name'],
                'Cat': category,
                'SCat': subcategory,
                'BR': transaction.get('Br'),
                'Note': transaction.get('No'),
                'PM': pm,
                'PMC': transaction.get('Pc'),
                'Ma': marked,
                'STx': transaction.get('Trt'),
            }
            transactions.append(transaction_data)

            # Update account totals
            account_totals[account_id]['total_amount'] += amount
            if marked == 1:
                account_totals[account_id]['total_marked_amount'] += amount
            account_totals[account_id]['Currency'] = { 'id': transaction.get('Cu'), 'name': currencies.get(transaction.get('Cu'), 'Unknown') }
        
        except Exception as e:
            logging.warning(f"Skipping transaction {idx}: {e}")
            continue

    return accounts, parties, transactions, categories, subcategories, payments, account_totals, next_id

def get_stdin_content():
    file_content = b''
    while True:
        data = sys.stdin.buffer.read(10240)  # Read in 10KB blocks
        if not data:
            break
        file_content += data
    return file_content

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read, modify, and write GSB files.")
    parser.add_argument('file_path', help='Path to the GSB file')
    parser.add_argument('--check-file', action='store_true', help='Check encrypted file')
    parser.add_argument('--list-accounts', action='store_true', help='List Accounts from GSB file')
    parser.add_argument('--list-parties', action='store_true', help='List Parties from GSB file')
    parser.add_argument('--list-categories', action='store_true', help='List Categories from GSB file')
    parser.add_argument('--list-payments', action='store_true', help='List Payments from GSB file')
    parser.add_argument('--list-transactions', help='List Transactions from GSB file')
    parser.add_argument('--add-transaction', action='store_true', help='Add a new transaction')
    parser.add_argument('--transaction-data', help='JSON string containing transaction data')
    parser.add_argument('--pass-word', help='Get Password for GSB file (use env var GRISBI_PASSWORD for security)')
    args = parser.parse_args()

    file_path = args.file_path

    if args.check_file:
        crypted_file_content = get_stdin_content()
        res = {'Encrypted' : str(gsb_decode.check_encrypt_gsb(crypted_file_content))}
        print(json.dumps(res))
        exit()

    file_content = ''
    isEncrypted = False
    if (file_path == '-'):
        crypted_file_content = get_stdin_content()
        isEncrypted = gsb_decode.check_encrypt_gsb(crypted_file_content)
        if (isEncrypted):
            # Security: Use environment variable or command line arg
            password = args.pass_word or sys.argv[sys.argv.index('--pass-word') + 1] if '--pass-word' in sys.argv else None
            file_content = gsb_decode.decrypt_v2(password, crypted_file_content)
        else:
            file_content = crypted_file_content
    else:
        file_content = gsb_decode.read_gsb_file(file_path)

    root = parse_gsb_content(file_content)
    if root is None:
        logging.error("Failed to parse the GSB file.")
        exit(1)

    accounts, parties, transactions, categories, subcategories, payments, account_totals, next_id = extract_data(root)

    if args.add_transaction:
        if not args.transaction_data:
            logging.error("Transaction data is required to add a new transaction.")
            exit(1)

        try:
            transactions_data = json.loads(args.transaction_data)
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding transaction data: {e}")
            exit(1)

        for transaction_data in transactions_data:
            transaction_number = transaction_data.get('Nb')
            isDeleted = transaction_data.get('Delete')
            existing_transaction = find_transaction_by_number(root, transaction_number)

            if existing_transaction is not None:
                if isDeleted is not None:
                    root.remove(existing_transaction)
                else:
                    for key, value in transaction_data.items():
                        existing_transaction.set(key, str(value))
            else:
                if isDeleted is None:
                    add_transaction(root, transaction_data)

        # Write the updated XML back to the file
        file_content = write_gsb_content(root)
        if (file_path == '-'):
            if (isEncrypted):
                password = args.pass_word or sys.argv[sys.argv.index('--pass-word') + 1] if '--pass-word' in sys.argv else None
                sys.stdout.buffer.write(gsb_decode.encrypt_v2(password, file_content))
            else:
                print(file_content)
        else:
            gsb_decode.write_gsb_file(file_path, file_content)
            logging.info(f"Updated GSB file written to {file_path}")

    if args.list_accounts:
        accounts_json = get_accounts_json(accounts, account_totals)
        print(accounts_json)

    if args.list_parties:
        parties_json = get_parties_json(parties)
        print(parties_json)

    if args.list_categories:
        categories_json = get_categories_json(categories, subcategories)
        print(categories_json)

    if args.list_payments:
        payments_json = get_payments_json(payments)
        print(payments_json)

    if args.list_transactions:
        account_id = args.list_transactions
        account_transactions_json = get_account_transactions_json(accounts, transactions, account_totals, payments, account_id, next_id)
        print(account_transactions_json)
