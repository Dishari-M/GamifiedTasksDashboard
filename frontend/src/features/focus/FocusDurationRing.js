import { useCallback, useMemo, useRef, useState } from "react";

export const FOCUS_DURATION_MIN = 15;
export const FOCUS_DURATION_MAX = 120;
export const FOCUS_DURATION_STEP = 5;
export const FOCUS_DURATION_DEFAULT = 25;
export const FOCUS_DURATION_SNAP_POINTS = [15, 25, 45, 60, 90];

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const RING_VIEWBOX = 120;
const RING_CENTER = RING_VIEWBOX / 2;
const RING_RADIUS = 45;
const RING_STROKE_WIDTH = 16;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

export const clampFocusDurationMinutes = (value, fallback = FOCUS_DURATION_DEFAULT) => {
  const parsed = Number(value);
  const safeValue = Number.isFinite(parsed) ? parsed : fallback;
  const stepped = Math.round(safeValue / FOCUS_DURATION_STEP) * FOCUS_DURATION_STEP;
  return clamp(stepped, FOCUS_DURATION_MIN, FOCUS_DURATION_MAX);
};

const snapFocusDurationMinutes = (value) => {
  const stepped = clampFocusDurationMinutes(value);
  const nearbySnap = FOCUS_DURATION_SNAP_POINTS.find((point) => Math.abs(point - stepped) <= FOCUS_DURATION_STEP / 2);
  return nearbySnap || stepped;
};

export const focusDurationProfile = (minutes = FOCUS_DURATION_DEFAULT) => {
  const value = clampFocusDurationMinutes(minutes);
  if (value >= 90) {
    return {
      tone: "flow",
      label: "Flow State",
      start: "#ffcc66",
      end: "#ff4fd8",
      glow: "rgba(255, 113, 198, 0.42)",
    };
  }
  if (value > 25) {
    return {
      tone: "deep",
      label: "Deep Work",
      start: "#7b61ff",
      end: "#20c7ff",
      glow: "rgba(112, 71, 255, 0.36)",
    };
  }
  return {
    tone: "light",
    label: "Light Focus",
    start: "#5df2a0",
    end: "#20c7ff",
    glow: "rgba(32, 199, 255, 0.26)",
  };
};

const durationToProgress = (minutes) => (
  (clampFocusDurationMinutes(minutes) - FOCUS_DURATION_MIN) / (FOCUS_DURATION_MAX - FOCUS_DURATION_MIN)
);

const pointOnRing = (angleDegrees, radius = RING_RADIUS) => {
  const radians = ((angleDegrees - 90) * Math.PI) / 180;
  return {
    x: RING_CENTER + radius * Math.cos(radians),
    y: RING_CENTER + radius * Math.sin(radians),
  };
};

const durationFromPointer = (event, element) => {
  const rect = element.getBoundingClientRect();
  const centerX = rect.left + rect.width / 2;
  const centerY = rect.top + rect.height / 2;
  const x = event.clientX - centerX;
  const y = event.clientY - centerY;
  const angle = (Math.atan2(y, x) * 180) / Math.PI;
  const clockwiseFromTop = (angle + 90 + 360) % 360;
  const rawValue = FOCUS_DURATION_MIN + (clockwiseFromTop / 360) * (FOCUS_DURATION_MAX - FOCUS_DURATION_MIN);
  return snapFocusDurationMinutes(rawValue);
};

const markerLine = (point) => {
  const angle = durationToProgress(point) * 360;
  const outer = pointOnRing(angle, RING_RADIUS + RING_STROKE_WIDTH / 2 - 3);
  const inner = pointOnRing(angle, RING_RADIUS + RING_STROKE_WIDTH / 2 - 10);
  return { x1: inner.x, y1: inner.y, x2: outer.x, y2: outer.y };
};

const FocusDurationRing = ({ value, onChange, disabled = false, compact = false, "data-testid": testId = "focus-duration-ring" }) => {
  const ringRef = useRef(null);
  const pointerIdRef = useRef(null);
  const gradientIdRef = useRef(`focus-ring-gradient-${Math.random().toString(36).slice(2)}`);
  const [isDragging, setIsDragging] = useState(false);
  const duration = clampFocusDurationMinutes(value);
  const profile = useMemo(() => focusDurationProfile(duration), [duration]);
  const progress = durationToProgress(duration);
  const handleAngle = progress * 360;
  const handlePoint = pointOnRing(handleAngle);
  const dashOffset = RING_CIRCUMFERENCE * (1 - progress);

  const updateFromPointer = useCallback((event) => {
    if (disabled || !ringRef.current) return;
    onChange?.(durationFromPointer(event, ringRef.current));
  }, [disabled, onChange]);

  const handlePointerDown = (event) => {
    if (disabled || !ringRef.current) return;
    pointerIdRef.current = event.pointerId;
    ringRef.current.setPointerCapture?.(event.pointerId);
    setIsDragging(true);
    updateFromPointer(event);
    event.preventDefault();
  };

  const handlePointerMove = (event) => {
    if (!isDragging || pointerIdRef.current !== event.pointerId) return;
    updateFromPointer(event);
    event.preventDefault();
  };

  const endPointerDrag = (event) => {
    if (pointerIdRef.current !== event.pointerId) return;
    ringRef.current?.releasePointerCapture?.(event.pointerId);
    pointerIdRef.current = null;
    setIsDragging(false);
  };

  const adjustDuration = (delta) => {
    if (disabled) return;
    onChange?.(clampFocusDurationMinutes(duration + delta));
  };

  const handleKeyDown = (event) => {
    if (disabled) return;
    const step = event.shiftKey ? 15 : FOCUS_DURATION_STEP;
    if (event.key === "ArrowRight" || event.key === "ArrowUp") {
      event.preventDefault();
      adjustDuration(step);
    } else if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
      event.preventDefault();
      adjustDuration(-step);
    } else if (event.key === "Home") {
      event.preventDefault();
      onChange?.(FOCUS_DURATION_MIN);
    } else if (event.key === "End") {
      event.preventDefault();
      onChange?.(FOCUS_DURATION_MAX);
    }
  };

  return (
    <div
      ref={ringRef}
      className={`focus-duration-ring focus-duration-${profile.tone}${compact ? " focus-duration-compact" : ""}${isDragging ? " is-dragging" : ""}${disabled ? " is-disabled" : ""}`}
      role="slider"
      tabIndex={disabled ? -1 : 0}
      aria-label="Focus session duration"
      aria-valuemin={FOCUS_DURATION_MIN}
      aria-valuemax={FOCUS_DURATION_MAX}
      aria-valuenow={duration}
      aria-valuetext={`${duration} minutes, ${profile.label}`}
      aria-disabled={disabled}
      data-testid={testId}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={endPointerDrag}
      onPointerCancel={endPointerDrag}
      onKeyDown={handleKeyDown}
      style={{
        "--focus-duration-progress": `${handleAngle}deg`,
        "--focus-ring-handle-angle": `${handleAngle}deg`,
        "--focus-ring-start": profile.start,
        "--focus-ring-end": profile.end,
        "--focus-ring-glow": profile.glow,
      }}
    >
      <svg className="focus-duration-ring-svg" viewBox={`0 0 ${RING_VIEWBOX} ${RING_VIEWBOX}`} aria-hidden="true">
        <defs>
          <linearGradient id={gradientIdRef.current} x1="18" y1="102" x2="102" y2="18" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor={profile.start} />
            <stop offset="100%" stopColor={profile.end} />
          </linearGradient>
        </defs>
        <circle
          className="focus-duration-ring-track"
          cx={RING_CENTER}
          cy={RING_CENTER}
          r={RING_RADIUS}
          strokeWidth={RING_STROKE_WIDTH}
        />
        <circle
          className="focus-duration-ring-arc"
          cx={RING_CENTER}
          cy={RING_CENTER}
          r={RING_RADIUS}
          stroke={`url(#${gradientIdRef.current})`}
          strokeWidth={RING_STROKE_WIDTH}
          strokeDasharray={RING_CIRCUMFERENCE}
          strokeDashoffset={dashOffset}
        />
        {FOCUS_DURATION_SNAP_POINTS.map((point) => {
          const line = markerLine(point);
          return (
            <line
              key={point}
              className={`focus-duration-marker${duration === point ? " active" : ""}`}
              x1={line.x1}
              y1={line.y1}
              x2={line.x2}
              y2={line.y2}
            />
          );
        })}
        <circle className="focus-duration-ring-handle-glow" cx={handlePoint.x} cy={handlePoint.y} r="9.5" />
        <circle className="focus-duration-ring-handle" cx={handlePoint.x} cy={handlePoint.y} r="5.9" />
      </svg>
      <span className="focus-duration-ring-center">
        <strong>{duration}m</strong>
      </span>
    </div>
  );
};

export default FocusDurationRing;
