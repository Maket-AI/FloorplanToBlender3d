# FROM public.ecr.aws/lambda/python:3.8

# RUN yum install -y mesa-libGL

# # Copy necessary Python files and requirements
# # COPY floorplan_detector/app.py floorplan_detector/detector.py floorplan_detector/call_blender3d.py floorplan_detector/utils floorplan_detector/requirements.txt ./
# COPY app.py detector.py call_blender3d.py utils requirements.txt ./

# # Copy the FloorplanToBlenderLib if needed
# COPY FloorplanToBlenderLib FloorplanToBlenderLib/

# # Install dependencies in the Lambda task root
# RUN pip3 install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# # Set the CMD to your handler function
# CMD ["app.lambda_handler"]
# First stage: Temporary image just to copy files from
FROM alpine as files
WORKDIR /temp
COPY ./FloorplanToBlenderLib ./FloorplanToBlenderLib

# Second stage: Actual Lambda image
FROM public.ecr.aws/lambda/python:3.8
RUN yum install -y mesa-libGL
# Copy files from the first stage
COPY --from=files /temp/FloorplanToBlenderLib ./FloorplanToBlenderLib
# Copy other necessary files
COPY ./floorplan_detector/app.py ./floorplan_detector/detector.py ./floorplan_detector/call_blender3d.py ./floorplan_detector/utils ./floorplan_detector/requirements.txt ./
# Install dependencies
RUN pip3 install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"
CMD ["app.lambda_handler"]
