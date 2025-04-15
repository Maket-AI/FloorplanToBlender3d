#!/usr/bin/env python3
import os
import sys
import json
import argparse
import glob
from pathlib import Path
import time
from test_raster_api import test_floor_plan_digitalization
from compare_methods import test_our_method, visualize_comparison

def batch_process(input_dir, output_dir=None, visualize=False):
    """
    Process multiple images in a directory.
    
    Args:
        input_dir (str): Directory containing the input images
        output_dir (str, optional): Directory to save the output. Defaults to None.
        visualize (bool, optional): Whether to visualize the comparison. Defaults to False.
    """
    # If no output directory is provided, use a default directory
    if not output_dir:
        output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "outputs"))
    
    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all image files in the input directory
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        image_files.extend(glob.glob(os.path.join(input_dir, ext)))
    
    # Process each image
    results = []
    for image_path in image_files:
        print(f"\nProcessing image: {image_path}")
        
        # Test the raster API
        print("Testing Raster API...")
        raster_result = test_floor_plan_digitalization(image_path, output_dir)
        
        # Test our method
        print("Testing our method...")
        our_result = test_our_method(image_path, output_dir)
        
        # Visualize the comparison if requested
        if visualize and raster_result and our_result:
            print("Visualizing comparison...")
            visualize_comparison(image_path, raster_result, our_result, output_dir)
        
        # Store the results
        results.append({
            'image': os.path.basename(image_path),
            'raster_api_rooms': len(raster_result.get('rooms', [])) if raster_result else 0,
            'our_method_rooms': len(our_result['data']['plans'][0]) if our_result and 'data' in our_result and 'plans' in our_result['data'] else 0
        })
        
        # Sleep to avoid rate limiting
        time.sleep(1)
    
    # Save the summary to a JSON file
    summary_file = os.path.join(output_dir, 'batch_summary.json')
    with open(summary_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nBatch processing complete. Summary saved to {summary_file}")
    
    # Print a summary
    print("\nSummary:")
    for result in results:
        print(f"{result['image']}: Raster API detected {result['raster_api_rooms']} rooms, Our method detected {result['our_method_rooms']} rooms")

def main():
    parser = argparse.ArgumentParser(description='Batch process floor plan images')
    parser.add_argument('--input', type=str, help='Directory containing the input images')
    parser.add_argument('--output', type=str, help='Directory to save the output')
    parser.add_argument('--visualize', action='store_true', help='Visualize the comparison')
    parser.add_argument('--api-key', type=str, help='RapidAPI key')
    args = parser.parse_args()
    
    # If API key is provided, set it as an environment variable
    if args.api_key:
        os.environ["RAPIDAPI_KEY"] = args.api_key
    
    # If no input directory is provided, use the events directory
    if not args.input:
        args.input = os.path.abspath(os.path.join(os.path.dirname(__file__), "../events"))
    
    # If no output directory is provided, use a default directory
    if not args.output:
        args.output = os.path.abspath(os.path.join(os.path.dirname(__file__), "outputs"))
    
    print(f"Processing images in: {args.input}")
    batch_process(args.input, args.output, args.visualize)

if __name__ == "__main__":
    main() 