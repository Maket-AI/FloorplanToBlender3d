import json
import os
import logging
from process_results_from_raster import ElementProcessor, FloorplanVisualizer

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_processing_with_sample_data():
    """
    Test the updated door and window processing function with sample data.
    """
    print("Testing the updated door and window processing...")
    
    # Check for example data
    script_dir = os.path.dirname(os.path.abspath(__file__))
    example_file = os.path.join(script_dir, 'outputs', 'example_simple_result.json')
    
    try:
        with open(example_file, 'r') as f:
            example_data = json.load(f)
            print(f"Loaded test data from {example_file}")
    except FileNotFoundError:
        print(f"Error: {example_file} not found. Creating sample data...")
        # Create sample data if file not found
        example_data = {
            "walls": [
                {"position": [[0, 0], [100, 0]]},
                {"position": [[100, 0], [100, 100]]},
                {"position": [[100, 100], [0, 100]]},
                {"position": [[0, 100], [0, 0]]}
            ],
            "doors": [
                {"bbox": [[40, -5], [60, -5], [60, 5], [40, 5]]},
                {"bbox": [[95, 40], [105, 40], [105, 60], [95, 60]]},
                {"bbox": [[30, 95], [70, 95], [70, 105], [30, 105]]},
                {"bbox": [[-5, 30], [-5, 70], [5, 70], [5, 30]]}
            ]
        }
    
    # Process with the updated function
    processor = ElementProcessor()
    processed_result = processor.process_result_for_frontend(example_data)
    
    # Print some results
    print(f"\nProcessed {len(processed_result.get('doors', []))} doors")
    print(f"Processed {len(processed_result.get('windows', []))} windows")
    
    # Now run the visualization to compare with previous implementation
    FloorplanVisualizer.test_door_window_processing_with_visualization()
    
    print("\nTest completed. Check the output files in the 'outputs' directory:")
    print("1. processed_elements.json - Frontend-ready data")
    print("2. detailed_processing.json - Detailed processing data")
    print("3. metadata_visualization.png - Visualization of the processed data")

if __name__ == "__main__":
    test_processing_with_sample_data() 