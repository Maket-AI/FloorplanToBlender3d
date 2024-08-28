import boto3
from decimal import Decimal
from collections import defaultdict
import pandas as pd
import time
import random
import json
from tqdm import tqdm

class RetrieveEditorData:
    def __init__(self, table_name='editor-data', region_name='ca-central-1'):
        self.table_name = table_name
        self.region_name = region_name
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region_name)
        self.table = self.dynamodb.Table(self.table_name)

    def convert_decimals(self, item):
        """Recursively converts Decimal fields to int or float."""
        if isinstance(item, list):
            return [self.convert_decimals(i) for i in item]
        elif isinstance(item, dict):
            return {k: self.convert_decimals(v) for k, v in item.items()}
        elif isinstance(item, Decimal):
            return int(item) if item == item.to_integral_value() else float(item)
        else:
            return item

    def retrieve_and_save_data(self, filename='dynamodb_data.json'):
        """Retrieve all data from DynamoDB and save it locally."""
        data = self.retrieve_all_data()
        self.save_data_locally(data, filename)

    def retrieve_all_data(self, limit=100, max_retries=10):
        """Retrieve all data from the table with pagination handling and a limit."""
        items = []
        retries = 0
        total_items = 0

        while retries < max_retries:
            try:
                response = self.table.scan(Limit=limit)
                items.extend(response.get('Items', []))
                total_items += len(response.get('Items', []))
                print(f"Processed {total_items} items so far...")

                # Handle pagination
                while 'LastEvaluatedKey' in response:
                    response = self.table.scan(ExclusiveStartKey=response['LastEvaluatedKey'], Limit=limit)
                    items.extend(response.get('Items', []))
                    total_items += len(response.get('Items', []))
                    print(f"Processed {total_items} items so far...")

                print(f"Data retrieval complete. Total items processed: {total_items}")
                return [self.convert_decimals(item) for item in items]

            except boto3.exceptions.botocore.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'ProvisionedThroughputExceededException':
                    retries += 1
                    sleep_time = (2 ** retries) + random.uniform(0, 1)
                    print(f"Provisioned throughput exceeded. Retrying in {sleep_time:.2f} seconds...")
                    time.sleep(sleep_time)
                else:
                    print(f"Error occurred: {e}")
                    return []
        
        print(f"Max retries exceeded. Could not retrieve all data. Total items processed: {total_items}")
        return []

    def save_data_locally(self, data, filename='dynamodb_data.json'):
        """Save the retrieved data locally as a JSON file."""
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Data saved locally to {filename}")

    def load_data_locally(self, filename='dynamodb_data.json'):
        """Load the data from a local JSON file."""
        with open(filename, 'r') as f:
            data = json.load(f)
        print(f"Data loaded from local file {filename}")
        return data

    def perform_analysis(self, data):
        """Perform analysis on the loaded data."""
        # Count total items
        total_items = self.count_total_items(data)
        print(f"Total number of items: {total_items}")
        
        # 1. Count unique users
        unique_users_count = self.count_unique_users(data)
        print(f"Unique users: {unique_users_count}")

        # 2. Get unique designs and count versions
        unique_designs = self.get_unique_designs(data)
        unique_designs_count = len(unique_designs)
        print(f"Unique designIDs: {unique_designs_count}")
        if unique_designs_count > 0:
            example_design_id = next(iter(unique_designs))
            versions_count = self.count_versions_per_design(data, example_design_id)
            print(f"Versions for designId {example_design_id}: {versions_count}")

        # 3. Count unique designs per flow
        unique_designs_per_flow = self.count_unique_designs_per_flow(data)
        print(f"Unique designIDs per flow: {unique_designs_per_flow}")

        # 4. Calculate versions per flow for GENERATED_PLAN and RECOGNIZED_PLAN
        for flow_type in ['GENERATED_PLAN', 'RECOGNIZED_PLAN']:
            num_designs, avg_versions = self.calculate_versions_per_flow(data, flow_type)
            print(f"Flow: {flow_type}, Number of designIDs: {num_designs}, Average versions per designID: {avg_versions}")

        # 5. Create and save a sub-dataset for GENERATED_PLAN
        sub_dataset = self.create_sub_dataset(data, 'GENERATED_PLAN')
        self.save_dataset(sub_dataset, 'generated_plan_sub_dataset.csv')

    def count_total_items(self, data):
        """Counts the total number of data entries."""
        return len(data)

    def count_unique_users(self, data):
        """Count unique userIDs."""
        unique_users = set(item['userID'] for item in data if 'userID' in item)
        return len(unique_users)

    def get_unique_designs(self, data):
        """Return a set of unique designIDs, handling missing keys."""
        unique_designs = set(item.get('designId') for item in data if 'designId' in item)
        return unique_designs

    def count_versions_per_design(self, data, design_id):
        """Count the number of versions for a given designId."""
        versions = [item['version'] for item in data if item.get('designId') == design_id]
        return len(versions)

    def count_unique_designs_per_flow(self, data):
        """Count the number of unique designIDs in each flow."""
        flow_counts = defaultdict(set)
        for item in data:
            if 'flow' not in item:
                print(f"Warning: Missing 'flow' key in item {item}")
                continue
            if 'designId' in item:
                flow_counts[item['flow']].add(item['designId'])
        return {flow: len(designs) for flow, designs in flow_counts.items()}

    def calculate_versions_per_flow(self, data, flow_type):
        """Calculate the number of versions per designID in a given flow."""
        designs = defaultdict(list)
        for item in tqdm(data):
            if 'flow' not in item:
                print(f"Warning: Missing 'flow' key in item {item}")
                continue
            if item['flow'] == flow_type and 'designId' in item:
                designs[item['designId']].append(item['version'])
            else:
                if 'designId' not in item:
                    print(f"Warning: Missing 'designId' key in item {item}")
        
        total_versions = sum(len(versions) for versions in designs.values())
        num_designs = len(designs)
        return num_designs, total_versions / num_designs if num_designs > 0 else 0

    def create_sub_dataset(self, data, flow_type):
        """Create a sub-dataset for the first and last versions of each designId in a given flow."""
        sub_dataset = []
        designs = defaultdict(list)
        
        for item in data:
            if 'flow' not in item:
                print(f"Warning: Missing 'flow' key in item ")
                continue
            if item['flow'] == flow_type and 'designId' in item:
                designs[item['designId']].append(item)
            else:
                if 'designId' not in item:
                    print(f"Warning: Missing 'designId' key in item {item}")
        for design_id, items in designs.items():
            items.sort(key=lambda x: x['savedAt'])
            sub_dataset.append(items[0])  # First version (earliest)
            sub_dataset.append(items[-1]) # Last version (latest)
        return sub_dataset

    def save_dataset(self, data, filename):
        """Save the dataset to a CSV file."""
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        print(f"Dataset saved to {filename}")

# Example usage
if __name__ == "__main__":
    retriever = RetrieveEditorData()

    # Step 1: Retrieve data and save it locally
    # retriever.retrieve_and_save_data('dynamodb_data.json')

    # Step 2: Load data and perform analysis
    data = retriever.load_data_locally('dynamodb_data.json')
    retriever.perform_analysis(data)
