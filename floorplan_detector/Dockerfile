FROM public.ecr.aws/lambda/python:3.8

RUN yum install -y mesa-libGL

# Copy necessary Python files and requirements
COPY floorplan_detector/app.py floorplan_detector/detector.py floorplan_detector/merge_walls.py floorplan_detector/requirements.txt ./

# Copy the FloorplanToBlenderLib if needed
COPY FloorplanToBlenderLib FloorplanToBlenderLib/

# Install dependencies in the Lambda task root
RUN pip3 install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Set the CMD to your handler function
CMD ["app.lambda_handler"]
