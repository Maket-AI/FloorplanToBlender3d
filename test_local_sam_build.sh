#!/bin/bash

# Exit on error
set -e

echo "Testing SAM build locally..."

# Create necessary directories if they don't exist
mkdir -p Recognizer_Demo/raster_api/.elasticbeanstalk/logs
touch Recognizer_Demo/raster_api/.elasticbeanstalk/logs/latest

# Run SAM build
echo "Running SAM build..."
sam build --template-file template.yml

echo "SAM build completed successfully!"
echo "You can now commit your changes to GitHub." 