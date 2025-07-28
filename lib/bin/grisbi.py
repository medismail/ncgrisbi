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
    """Find a transaction element by its 'Nb' attribute."""
    if transaction_number is None:
        return None
    for transaction in root.findall('.//Transaction'):
        if transaction.get('Nb') == str(transaction_number):
            return transaction
    return None


#{"Ac":"8","Nb":"2685","Id":"(null)","Dt":"06/25/2022","Dv":"(null)","Cu":"1","Am":"1000.00","Exb":"0","Exr":"0.00","Exf":"0.00","Pa":"190","Ca":"0","Sca":"0","Br":"0","No":"(null)","Pn":"0","Pc":"(null)","Ma":"0","Ar":"0","Au":"0","Re":"0","Fi":"0","Bu":"0","Sbu":"0","Vo":"(null)","Ba":"(null)","Trt":"0","Mo":"0"}
def add_transaction(root, transaction_data):
    """Add a new transaction to the XML root element immediately after the last transaction."""
    transaction = ET.Element('Transaction')
    for key, value in transaction_data.items():
        transaction.set(key, value)
#   ET.dump(transaction)
   
    # 1. Find the last <Transaction> element (if any)
    last_transaction = None
    last_transaction = root.find('.//Transaction[last()]')

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
    partie_list = [{'id': partie_id, 'name': partie_info['name'], 'last_amount': partie_info['last_amount'], 'last_category': partie_info['last_category'], 'last_subcategory': partie_info['last_subcategory']} for partie_id, partie_info in parties.items()]
    return json.dumps(partie_list, indent=4)

def get_categories_json(categories, subcategories):
    """
    categories   : dict  {cat_id: cat_name}
    subcategories: dict  {cat_id: [{'id':..., 'name':...}, ...]}
    """
    #categorie_list = [{'id': categorie_id, 'name': categorie_name, 'subcategories': [{'id': sc_id, 'name': sc_name} for (c_id, sc_id), sc_name in subcategories.items() if c_id == categorie_id]} for categorie_id, categorie_name in categories.items()]
    categorie_list = [{'id': cid, 'name': cname, 'subcategories': subcategories.get(cid, [])} for cid, cname in categories.items()]
    return json.dumps(categorie_list)

def get_payments_json(payments):
    payment_list = [{'id': payment_id, 'name': payment_info['name'], 'account': payment_info['account']} for payment_id, payment_info in payments.items()]
    return json.dumps(payment_list, indent=4)

def get_accounts_json(accounts, account_totals):
    #account_list = [{'id': account_id, 'name': account_info['name'], 'bank': account_info['bank'], 'type': account_info['type'], 'currency': account_info['currency'], 'total': account_totals.get(account_id, {'total_amount': 0.0, 'total_marked_amount': 0.0})} for account_id, account_info in accounts.items()]
    account_list = [{'id': account_id, 'name': account_info['name'], 'bank': account_info['bank'], 'type': account_info['type'], 'currency': account_info['currency'], 'total': {'total_amount': float(round(account_totals[account_id]['total_amount'], 2)), 'total_marked_amount': float(round(account_totals[account_id]['total_marked_amount'], 2))}} for account_id, account_info in accounts.items()]
    return json.dumps(account_list)

def get_account_transactions_json(accounts, transactions, account_totals, payments, account_id, next_id):
    account_transactions = [tx for tx in transactions if tx['Account'] == accounts.get(account_id, {'name': 'Unknown', 'bank': 'Unknown'})['name']]
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
    """Extract data from the XML root element."""
    # Extract currencies
    currencies = {}
    for currency in root.findall('Currency'):
        currency_id = currency.get('Nb')
        currency_iso_name = currency.get('Ico')
        currencies[currency_id] = currency_iso_name

    # Extract parties (payees)
    parties = {}
    for party in root.findall('Party'):
        party_id = party.get('Nb')
        party_name = party.get('Na')
        parties[party_id] = { 'name': party_name, 'last_amount': 0, 'last_category': '', 'last_subcategory': '' }

    # Extract categories and subcategories
    categories = {}
    subcategories_name_map = {}
    subcategories = defaultdict(list)
    for category in root.findall('Category'):
        category_id = category.get('Nb')
        category_name = category.get('Na')
        categories[category_id] = category_name

    for subcategory in root.findall('Sub_category'):
        category_id = subcategory.get('Nbc')
        subcategory_id = subcategory.get('Nb')
        subcategory_name = subcategory.get('Na')
        subcategories_name_map[(category_id, subcategory_id)] = subcategory_name
        subcategories[category_id].append({'id': subcategory_id, 'name': subcategory_name})

    # Extract payment methods
    payments = {}
    #payments['0'] = { 'name': 'Unknown', 'account': '0' }
    for payment in root.findall('Payment'):
        payment_number = payment.get('Number')
        payments[payment_number] = {
            'name': payment.get('Name'),
            'account': payment.get('Account')
        }

    # Extract banks and map account IDs to bank names
    banks = {}
    banks['-1'] = 'N/A'
    for bank in root.findall('Bank'):
        bank_number = bank.get('Nb')
        bank_name = bank.get('Na')
        banks[bank_number] = bank_name

    # Extract accounts and map account IDs to account names
    gsb_account_type = {"-1": "BALANCE", "0": "BANK", "1": "CASH", "2": "LIABILITIES", "3": "ASSET"}
    accounts = {}
    for account in root.findall('Account'):
        account_id = account.get('Number')
        account_name = account.get('Name')
        account_kind = account.get('Kind')
        account_currency = account.get('Currency')
        bank_number = account.get('Bank')  # Get the Bank attribute from the Account element
        accounts[account_id] = {
            'name': account_name,
            'bank': bank_number,
            'type': gsb_account_type[account_kind],
            'currency': currencies[account_currency]
        }

    # Initialize counters for each account
    account_totals = {}
    for account_id in accounts:
        account_totals[account_id] = {'total_amount': Decimal('0.0'), 'total_marked_amount': Decimal('0.0')}

    # Extract transactions
    next_id = 0
    transactions = []
    for transaction in root.findall('Transaction'):
        account_id = transaction.get('Ac')
        amount = Decimal(transaction.get('Am', '0.00'))
        marked = int(transaction.get('Ma', '0'))
        next_id = transaction.get('Nb')
        party_id = transaction.get('Pa')
        category = categories.get(transaction.get('Ca'), 'Uncategorized')
        subcategory = subcategories_name_map.get((transaction.get('Ca'), transaction.get('Sca')), 'Uncategorized')
        #if party_id and party_id in parties:
        if int(party_id):
            parties[party_id]['last_amount'] = float(amount)
            parties[party_id]['last_category'] = category
            parties[party_id]['last_subcategory'] = subcategory

        # Get account info including bank number
        account_info = accounts.get(account_id, {'name': 'Unknown', 'bank': 'Unknown'})
        bank_name = banks.get(account_info['bank'], 'Unknown')  # Look up the bank name

        transaction_data = {
            'Account': account_info['name'],
#            'Bank': banks.get(account_info['bank'], 'Unknown'),
            'Transaction Number': next_id,
#            'Transaction ID': transaction.get('Id'),
            'Date': transaction.get('Dt'),
#            'Value Date': transaction.get('Dv'),
            'Currency': currencies.get(transaction.get('Cu'), 'Unknown'),
            'Amount': float(amount),
#            'Change between account and transaction': transaction.get('Exb'),
#            'Exchange Rate': transaction.get('Exr'),
#            'Exchange Fee': transaction.get('Exf'),
            'Party': parties.get(party_id, { 'name': 'Unknown' })['name'],
            'Category': category,
            'Subcategory': subcategory,
            'Bank Reference': transaction.get('Br'),
            'Note': transaction.get('No'),
            'Payment Method': payments.get(transaction.get('Pn'), { 'name': 'Unknown' })['name'],
            'Payment Method Content': transaction.get('Pc'),
            'Marked': marked,
#            'Archive Number': transaction.get('Ar'),
#            'Automatic Transaction': transaction.get('Au'),
#            'Reconcile Number': transaction.get('Re'),
#            'Financial Year': transaction.get('Fi'),
#            'Budgetary Number': transaction.get('Bu'),
#            'Subbudgetary Number': transaction.get('Sbu'),
#            'Voucher': transaction.get('Vo'),
#            'Bank References': transaction.get('Ba'),
            'Split Transaction': transaction.get('Trt'),
#            'Mother Transaction Number': transaction.get('Mo'),
        }
        transactions.append(transaction_data)

        # Update account totals
        account_totals[account_id]['total_amount'] += amount
        if marked == 1:
            account_totals[account_id]['total_marked_amount'] += amount
        account_totals[account_id]['Currency'] = currencies.get(transaction.get('Cu'), 'Unknown')

    return accounts, parties, transactions, categories, subcategories, payments, account_totals, next_id

def get_stdin_content():
    file_content = b''
    while True:
        data = sys.stdin.buffer.read(1024)  # lecture par blocs de 1024 octets
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
    parser.add_argument('--pass-word', help='Get Password for GSB file')
    args = parser.parse_args()

    file_path = args.file_path

    if args.check_file:
        crypted_file_content = get_stdin_content()
        res = {'Encrypted' : str(gsb_decode.check_encrypt_gsb(crypted_file_content))}
        print(json.dumps(res))
        exit()

    file_content = ''
    if (file_path == '-'):
        crypted_file_content = get_stdin_content()
        if (gsb_decode.check_encrypt_gsb(crypted_file_content)):
            #password = input("Password: ")
            file_content = gsb_decode.decrypt_v2(args.pass_word, crypted_file_content)
        else:
            file_content = crypted_file_content
    else:
        #file_content = gsb_decode.read_gsb_file(sys.stdin)
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
            transaction_data = json.loads(args.transaction_data)
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding transaction data: {e}")
            exit(1)

        transaction_number = transaction_data.get('Transaction Number')
        existing_transaction = find_transaction_by_number(root, transaction_number)

        if existing_transaction is not None:
            for key, value in transaction_data.items():
                existing_transaction.set(key, str(value)) # Ensure value is a string for XML attribute
            logging.info(f"Transaction {transaction_number} updated successfully.")
        else:
            add_transaction(root, transaction_data)
            logging.info("New transaction added successfully.")

        # Write the updated XML back to the file
        file_content = write_gsb_content(root)
        gsb_decode.write_gsb_file(file_path, file_content)
        logging.info(f"Updated GSB file written to {file_path}")

    if args.list_accounts:
        # Get list of accounts in JSON format
        accounts_json = get_accounts_json(accounts, account_totals)
        #logging.info("Accounts JSON:")
        print(accounts_json)

    if args.list_parties:
        parties_json = get_parties_json(parties)
        #logging.info("\nParties JSON:")
        print(parties_json)

    if args.list_categories:
        categories_json = get_categories_json(categories, subcategories)
        print(categories_json)

    if args.list_payments:
        payments_json = get_payments_json(payments)
        print(payments_json)

    if args.list_transactions:
        # Get transactions for a specific account in JSON format
        account_id = args.list_transactions  # Example account ID
        account_transactions_json = get_account_transactions_json(accounts, transactions, account_totals, payments, account_id, next_id)
        #logging.info("\nAccount Transactions JSON:")
        print(account_transactions_json)
