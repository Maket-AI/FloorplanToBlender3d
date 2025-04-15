# Floor Plan Raster API

This folder contains scripts for testing and using the Floor Plan Digitalization API from RapidAPI. The API converts raster floor plan images into vectorized data with room detection and measurements.

## Features

- Convert raster floor plan images to vector data
- Detect rooms and their types
- Identify doors and their locations
- Calculate room areas and dimensions
- Support for both single image and batch processing

## Setup

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set up your RapidAPI key:
   - Get your API key from RapidAPI
   - Set it as an environment variable: `export RAPIDAPI_KEY=your_api_key`
   - Or provide it via command line: `--api-key your_api_key`

## Usage

### Single Image Processing

```bash
python test_raster_api.py --image path/to/your/floorplan.jpg
```

Options:
- `--image`: Path to the input floor plan image
- `--output`: Directory to save the output (default: ./outputs)
- `--api-key`: Your RapidAPI key

### Batch Processing

```bash
python batch_process.py --input-dir path/to/input/directory --output-dir path/to/output/directory
```

Options:
- `--input-dir`: Directory containing floor plan images
- `--output-dir`: Directory to save the results
- `--api-key`: Your RapidAPI key

## Output Format

The API returns a JSON object with the following structure:

```json
{
  "area": float,          // Total floor plan area
  "doors": [              // List of detected doors
    {
      "bbox": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]  // Door bounding box
    }
  ],
  "rooms": [              // List of detected rooms
    {
      "bbox": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]], // Room bounding box
      "type": string,     // Room type (e.g., "living_room", "dining_room")
      "id": int,          // Room ID
      "label": string,    // Room label
      "corners": [[x,y]], // Room corner coordinates
      "width": float,     // Room width
      "height": float     // Room height
    }
  ]
}
```

## API Documentation

The API is hosted on RapidAPI:
- Endpoint: `https://floor-plan-digitalization.p.rapidapi.com/raster-to-vector-base64`
- Method: POST
- Content-Type: application/json
- Required Headers:
  - X-RapidAPI-Key
  - X-RapidAPI-Host: floor-plan-digitalization.p.rapidapi.com

## Error Handling

The script handles common errors:
- 403: Invalid or missing API key
- 404: Invalid endpoint
- 400: Invalid request format
- 500: Server error

## License

This project is licensed under the MIT License - see the LICENSE file for details. 