import xml.etree.ElementTree as ET
import json
import gsb_decode

def parse_gsb_content(file_content):
    """Parse the XML content and return the root element."""
    if file_content is None:
        print("No content to parse.")
        return None

    try:
        # Parse the XML 
        tree = ET.ElementTree(ET.fromstring(file_content))
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return None

    # Extract currencies
    currencies = {}
    for currency in root.findall('Currency'):
        currency_id = currency.get('Nb')
        currency_name = currency.get('Na')
        currencies[currency_id] = currency_name

    # Extract parties (payees)
    parties = {}
    for party in root.findall('Party'):
        party_id = party.get('Nb')
        party_name = party.get('Na')
        parties[party_id] = party_name

    # Extract categories and subcategories
    categories = {}
    subcategories = {}
    for category in root.findall('Category'):
        category_id = category.get('Nb')
        category_name = category.get('Na')
        categories[category_id] = category_name

    for subcategory in root.findall('Sub_category'):
        category_id = subcategory.get('Nbc')
        subcategory_id = subcategory.get('Nb')
        subcategory_name = subcategory.get('Na')
        subcategories[(category_id, subcategory_id)] = subcategory_name

    # Extract payment methods
    payments = {}
    for payment in root.findall('Payment'):
        payment_number = payment.get('Number')
        payment_name = payment.get('Name')
        payments[payment_number] = payment_name

    # Extract accounts and map account IDs to account names
    accounts = {}
    for account in root.findall('Account'):
        account_id = account.get('Number')
        account_name = account.get('Name')
        accounts[account_id] = account_name

    # Initialize counters for each account
    account_totals = {}
    for account_id in accounts:
        account_totals[account_id] = {'total_amount': 0.0, 'total_marked_amount': 0.0}

    # Extract transactions
    transactions = []

    for transaction in root.findall('Transaction'):
        account_id = transaction.get('Ac')
        amount = float(transaction.get('Am', '0.00'))
        marked = int(transaction.get('Ma', '0'))

        transaction_data = {
            'Account': accounts.get(account_id, 'Unknown'),
            'Transaction Number': transaction.get('Nb'),
            'Transaction ID': transaction.get('Id'),
            'Date': transaction.get('Dt'),
            'Value Date': transaction.get('Dv'),
            'Currency': currencies.get(transaction.get('Cu'), 'Unknown'),
            'Amount': amount,
            'Exchange Basis': transaction.get('Exb'),
            'Exchange Rate': transaction.get('Exr'),
            'Exchange Fee': transaction.get('Exf'),
            'Party': parties.get(transaction.get('Pa'), 'Unknown'),
            'Category': categories.get(transaction.get('Ca'), 'Uncategorized'),
            'Subcategory': subcategories.get((transaction.get('Ca'), transaction.get('Sca')), 'Uncategorized'),
            'Bank Reference': transaction.get('Br'),
            'Note': transaction.get('No'),
            'Payment Method': payments.get(transaction.get('Pn'), 'Unknown'),
            'Payment Method Comment': transaction.get('Pc'),
            'Marked': marked,
            'Archived': transaction.get('Ar'),
            'Automatically Reconciled': transaction.get('Au'),
            'Reconciled': transaction.get('Re'),
            'Financial Year': transaction.get('Fi'),
            'Budgeted': transaction.get('Bu'),
            'Subbudgeted': transaction.get('Sbu'),
            'Voucher': transaction.get('Vo'),
            'Bank Account': transaction.get('Ba'),
            'Transaction Type': transaction.get('Trt'),
            'Memo Number': transaction.get('Mo'),
        }
        transactions.append(transaction_data)

        # Update account totals
        account_totals[account_id]['total_amount'] += amount
        if marked == 1:
            account_totals[account_id]['total_marked_amount'] += amount

    return accounts, transactions, account_totals

def get_accounts_json(accounts):
    account_list = [{'id': account_id, 'name': account_name} for account_id, account_name in accounts.items()]
    return json.dumps(account_list, indent=4)

def get_account_transactions_json(accounts, transactions, account_totals, account_id):
    account_transactions = [tx for tx in transactions if tx['Account'] == accounts.get(account_id, 'Unknown')]
    account_totals_data = account_totals.get(account_id, {'total_amount': 0.0, 'total_marked_amount': 0.0})

    result = {
        'account_id': account_id,
        'account_name': accounts.get(account_id, 'Unknown'),
        'transactions': account_transactions,
        'total_amount': round(account_totals_data['total_amount'], 2),
        'total_marked_amount': round(account_totals_data['total_marked_amount'], 2)
    }
    return json.dumps(result, indent=4)

if __name__ == "__main__":
    file_path = "decrypted_example.gsb"  # Update this path to your file

    file_content = gsb_decode.read_gsb_file(file_path)

    accounts, transactions, account_totals = parse_gsb_content(file_content)

    # Get list of accounts in JSON format
    accounts_json = get_accounts_json(accounts)
    print("Accounts JSON:")
    print(accounts_json)

    # Get transactions for a specific account in JSON format
    account_id = "8"  # Example account ID
    account_transactions_json = get_account_transactions_json(accounts, transactions, account_totals, account_id)
    print("\nAccount Transactions JSON:")
    print(account_transactions_json)
