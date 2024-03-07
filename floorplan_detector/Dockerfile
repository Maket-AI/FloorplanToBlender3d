# FROM public.ecr.aws/lambda/python:3.8

# RUN yum install -y mesa-libGL

# # Copy necessary Python files and requirements
# COPY floorplan_detector ./
# # COPY floorplan_detector/app.py floorplan_detector/detector.py floorplan_detector/call_blender3d.py floorplan_detector/utils floorplan_detector/requirements.txt ./
# # COPY app.py detector.py call_blender3d.py utils requirements.txt ./

# # Copy the FloorplanToBlenderLib if needed
# COPY FloorplanToBlenderLib FloorplanToBlenderLib/

# # Install dependencies in the Lambda task root
# RUN pip3 install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# # Set the CMD to your handler function
# CMD ["app.lambda_handler"]

# Use the base image provided by AWS Lambda for Python 3.8
FROM public.ecr.aws/lambda/python:3.8

# Install additional system dependencies
RUN yum install -y mesa-libGL

# Set the working directory to the Lambda task root (default is /var/task)
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy the FloorplanToBlenderLib directory to the Docker image
COPY FloorplanToBlenderLib FloorplanToBlenderLib/

# Copy the floorplan_detector directory to the Docker image
COPY floorplan_detector floorplan_detector/

# Copy the requirements file and install Python dependencies in the Lambda task root
COPY floorplan_detector/requirements.txt .
RUN pip3 install -r requirements.txt --target .

# Set the CMD to your handler function, adjust the path according to your project structure
CMD ["floorplan_detector.app.lambda_handler"]
