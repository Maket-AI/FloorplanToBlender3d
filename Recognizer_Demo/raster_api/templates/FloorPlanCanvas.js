import React, { useState, useRef } from 'react';
import { Stage, Layer, Line, Rect, Group, Text } from 'react-konva';

const FloorPlanCanvas = ({ data }) => {
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const stageRef = useRef();

  // Handle zoom with mouse wheel
  const handleWheel = (e) => {
    e.evt.preventDefault();
    const scaleBy = 1.1;
    const stage = stageRef.current;
    const oldScale = stage.scaleX();
    const pointer = stage.getPointerPosition();

    const mousePointTo = {
      x: (pointer.x - stage.x()) / oldScale,
      y: (pointer.y - stage.y()) / oldScale,
    };

    const newScale = e.evt.deltaY < 0 ? oldScale * scaleBy : oldScale / scaleBy;
    setScale(newScale);
    setPosition({
      x: pointer.x - mousePointTo.x * newScale,
      y: pointer.y - mousePointTo.y * newScale,
    });
  };

  // Handle drag
  const handleDragEnd = (e) => {
    setPosition({
      x: e.target.x(),
      y: e.target.y(),
    });
  };

  // Helper function to find nearest wall
  const findNearestWall = (point, walls) => {
    let nearestWall = null;
    let minDistance = Infinity;

    walls.forEach(wall => {
      const distance = pointToLineDistance(point, wall.start, wall.end);
      if (distance < minDistance) {
        minDistance = distance;
        nearestWall = wall;
      }
    });

    return nearestWall;
  };

  // Helper function to calculate point to line distance
  const pointToLineDistance = (point, lineStart, lineEnd) => {
    const A = point.x - lineStart.x;
    const B = point.y - lineStart.y;
    const C = lineEnd.x - lineStart.x;
    const D = lineEnd.y - lineStart.y;

    const dot = A * C + B * D;
    const lenSq = C * C + D * D;
    let param = -1;

    if (lenSq !== 0) param = dot / lenSq;

    let xx, yy;

    if (param < 0) {
      xx = lineStart.x;
      yy = lineStart.y;
    } else if (param > 1) {
      xx = lineEnd.x;
      yy = lineEnd.y;
    } else {
      xx = lineStart.x + param * C;
      yy = lineStart.y + param * D;
    }

    const dx = point.x - xx;
    const dy = point.y - yy;

    return Math.sqrt(dx * dx + dy * dy);
  };

  // Helper function to align object to wall
  const alignToWall = (point, wall) => {
    const angle = Math.atan2(wall.end.y - wall.start.y, wall.end.x - wall.start.x);
    return {
      x: point.x,
      y: point.y,
      rotation: angle * (180 / Math.PI),
    };
  };

  return (
    <Stage
      width={window.innerWidth}
      height={window.innerHeight}
      onWheel={handleWheel}
      ref={stageRef}
      scaleX={scale}
      scaleY={scale}
      x={position.x}
      y={position.y}
      draggable
      onDragEnd={handleDragEnd}
    >
      <Layer>
        {/* Draw walls */}
        {data.walls.map((wall, i) => (
          <Line
            key={`wall-${i}`}
            points={[wall.start.x, wall.start.y, wall.end.x, wall.end.y]}
            stroke="black"
            strokeWidth={2}
          />
        ))}

        {/* Draw doors */}
        {data.doors.map((door, i) => {
          const nearestWall = findNearestWall(door.position, data.walls);
          const aligned = alignToWall(door.position, nearestWall);
          return (
            <Group key={`door-${i}`} x={aligned.x} y={aligned.y} rotation={aligned.rotation}>
              <Rect
                width={30}
                height={5}
                fill="brown"
                stroke="black"
                strokeWidth={1}
              />
            </Group>
          );
        })}

        {/* Draw windows */}
        {data.windows.map((window, i) => {
          const nearestWall = findNearestWall(window.position, data.walls);
          const aligned = alignToWall(window.position, nearestWall);
          return (
            <Group key={`window-${i}`} x={aligned.x} y={aligned.y} rotation={aligned.rotation}>
              <Rect
                width={40}
                height={5}
                fill="lightblue"
                stroke="black"
                strokeWidth={1}
              />
            </Group>
          );
        })}

        {/* Draw measurements */}
        {data.walls.map((wall, i) => {
          const length = Math.sqrt(
            Math.pow(wall.end.x - wall.start.x, 2) +
            Math.pow(wall.end.y - wall.start.y, 2)
          );
          const midX = (wall.start.x + wall.end.x) / 2;
          const midY = (wall.start.y + wall.end.y) / 2;
          return (
            <Text
              key={`measurement-${i}`}
              x={midX}
              y={midY}
              text={`${Math.round(length)}cm`}
              fontSize={12}
              fill="black"
            />
          );
        })}
      </Layer>
    </Stage>
  );
};

export default FloorPlanCanvas; 