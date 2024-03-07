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

FROM public.ecr.aws/lambda/python:3.8

# Install necessary system dependencies
RUN yum install -y mesa-libGL

# Set the working directory in the container
WORKDIR /var/task

# Copy the FloorplanToBlenderLib and floorplan_detector directories
COPY FloorplanToBlenderLib ./FloorplanToBlenderLib
COPY floorplan_detector ./floorplan_detector

# Install Python dependencies
RUN pip3 install -r floorplan_detector/requirements.txt --target .

# Set the CMD to your handler (assuming app.py is within floorplan_detector and has a lambda_handler function)
CMD ["floorplan_detector.app.lambda_handler"]
