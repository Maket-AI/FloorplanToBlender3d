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

RUN yum install -y mesa-libGL

# Copy the entire floorplan_detector directory
COPY floorplan_detector /var/task/floorplan_detector

# Copy other necessary files
COPY requirements.txt /var/task/
COPY FloorplanToBlenderLib /var/task/FloorplanToBlenderLib/

# Install dependencies
RUN pip3 install -r /var/task/requirements.txt --target /var/task

# Set the CMD to your handler function
CMD ["floorplan_detector.app.lambda_handler"]
