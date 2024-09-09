import pandas as pd
import json
import ast

def preprocess_floorplan_data(file_path):
    """
    Preprocess the floorplan dataset to identify pairs of "generation" and "edited" versions
    and extract only the 'areas' and 'walls' information.

    Parameters:
    - file_path (str): Path to the CSV file containing the floorplan data.

    Returns:
    - pd.DataFrame: A processed DataFrame containing 'userID', 'designId', 'pair_index', 'areas', and 'walls'.
    """
    # Load the CSV file
    df = pd.read_csv(file_path)

    # Remove unnecessary columns
    df_cleaned = df.drop(columns=['flow', 'generationToken', 'saveID', 'source', 'thumbnail', 'generationIndex', 'floorplanID'])

    # Convert 'savedAt' to a numeric type to ensure correct sorting (if needed)
    df_cleaned['savedAt'] = pd.to_numeric(df_cleaned['savedAt'], errors='coerce')

    # Helper function to identify pairs
    def identify_pairs(group):
        # Find "generation" version (version == 1)
        generation = group[group['version'] == 1]
        # Find "edited" version (version > 1 or latest 'savedAt' if version is the same)
        edited = group[(group['version'] > 1) | (group['version'] == generation['version'].max())].sort_values('savedAt', ascending=False).head(1)
        
        # If no "edited" version is found, return empty DataFrame
        if edited.empty:
            return pd.DataFrame()

        # Assign labels for "generation" and "edited"
        generation['pair_index'] = 0
        edited['pair_index'] = 1

        return pd.concat([generation, edited])

    # Group by 'userID' and 'designId' and apply the pairing function
    df_pairs = df_cleaned.groupby(['userID', 'designId']).apply(identify_pairs).reset_index(drop=True)

    # Function to extract 'areas' and 'walls'
    def extract_areas_walls(row):
        try:
            data_list = ast.literal_eval(row['data'])
            
            areas, walls = None, None

            # Loop through each item to extract areas and walls
            for item in data_list:
                if 'designs' in item:
                    for design in item['designs']:
                        # Extract 'areas' and 'walls'
                        if 'areas' in design:
                            areas = design['areas']
                        if 'walls' in design:
                            walls = design['walls']
                        # If both 'areas' and 'walls' are found, break early
                        if areas and walls:
                            break
            return pd.Series({'areas': areas, 'walls': walls})
        
        except (json.JSONDecodeError, TypeError) as e:
            # Print the error and the problematic data for debugging
            print(f"Error parsing JSON: {e}")
            print(f"Problematic data: {row['data']}")
            return pd.Series({'areas': None, 'walls': None})

    # Apply the extraction function
    df_pairs[['areas', 'walls']] = df_pairs.apply(extract_areas_walls, axis=1)

    # Keep only the relevant columns
    df_final = df_pairs[['userID', 'designId', 'pair_index', 'areas', 'walls']]

    return df_final

# Example usage:
file_path = 'generated_plan_sub_dataset.csv'  # Adjust the path if necessary
processed_data = preprocess_floorplan_data(file_path)
processed_data.to_csv('processed_floorplan_data.csv', index=False)
print("Data preprocessing completed and saved to 'processed_floorplan_data.csv'.")
