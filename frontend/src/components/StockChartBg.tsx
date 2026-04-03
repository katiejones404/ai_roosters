import { useEffect, useRef } from "react";

// Visual settings for each animated line
const LINES = [
  { color: "#10b981", opacity: 0.55 }, // green line
  { color: "#6366f1", opacity: 0.55 }, // purple line
  { color: "#ef4444", opacity: 0.55 }, // red line
  { color: "#8b5cf6", opacity: 0.55 }, // lighter purple line
];

//How many points each line keeps in its sliding window
const NUM_POINTS = 100;

// How fast the chart scrolls horizontally
// Lower values make the motion feel smoother
const STEP_SPEED = 0.7;

// Random-walk step size for line movement
const VOLATILITY = 0.022;

export default function StockChartBg() {
  // Canvas DOM reference
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Resize canvas to always match the full browser view
    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    window.addEventListener("resize", resize);
    resize();

    // Build one random price-like series per line
    // Each series starts in a different vertical band so the lines do not overlap a lot
    const series = LINES.map((_, i) => {
      const base = 0.15 + i * 0.18; //Starting band for this line
      const pts: number[] = [];

      // Start each line near its base level.
      let v = base + Math.random() * 0.08;

      // Generate the initial window of points
      for (let j = 0; j < NUM_POINTS; j++) {
        // Random walk with clamping so values stay inside the chart area
        v = Math.max(
          0.05,
          Math.min(0.95, v + (Math.random() - 0.5) * VOLATILITY * 5)
        );
        pts.push(v);
      }

      return { pts, base };
    });

    //Horizontal scroll offset used to animate the chart
    let offset = 0;

    //for cleanup
    let rafId: number;

    // The chart uses only part of the full width so the right edge stays visible
    const CHART_WIDTH_RATIO = 0.9;

    // Draw one smoothed line using quadratic curves between points
    const drawSmooth = (pts: number[], w: number, h: number) => {
      if (pts.length < 2) return;

      const chartWidth = w * CHART_WIDTH_RATIO;
      const spacing = chartWidth / (NUM_POINTS - 1);

      // Apply a horizontal shift so the whole chart scrolls left over time
      const xs = pts.map((_, i) => i * spacing - (offset % spacing));

      // Convert normalized values into screen coordinates
      const ys = pts.map((v) => h * 0.05 + v * h * 0.9);

      ctx.beginPath();
      ctx.moveTo(xs[0], ys[0]);

      // Use quadratic curves to make the line smooth instead of jagged
      for (let i = 0; i < xs.length - 1; i++) {
        const mx = (xs[i] + xs[i + 1]) / 2;
        const my = (ys[i] + ys[i + 1]) / 2;
        ctx.quadraticCurveTo(xs[i], ys[i], mx, my);
      }

      ctx.lineTo(xs[xs.length - 1], ys[ys.length - 1]);
      ctx.stroke();
    };

    // Main animation loop.
    const draw = () => {
      const { width, height } = canvas;

      // Clear canvas so the page background gradient shows through
      ctx.clearRect(0, 0, width, height);

      // Compute one spacing step for the scrolling effect
      const spacing = (width * CHART_WIDTH_RATIO) / (NUM_POINTS - 1);

      // Draw each line with its own color + opacity.
      series.forEach(({ pts }, li) => {
        const { color, opacity } = LINES[li];

        ctx.save();
        ctx.strokeStyle = color;
        ctx.globalAlpha = opacity;
        ctx.lineWidth = 4;
        ctx.lineJoin = "round";
        ctx.lineCap = "round";

        drawSmooth(pts, width, height);

        ctx.restore();
      });

      // Move up the horizontal scroll position
      offset += STEP_SPEED;

      // When one full step has passed, shift each series left by one point
      // and then append a new point on the right side
      if (offset >= spacing) {
        offset -= spacing;

        series.forEach(({ pts, base }) => {
          const last = pts[pts.length - 1];

          // Keeps the line near its original band
          const pull = (base - last) * 0.05;

          // Generate the next point with a small random movement
          const next = Math.max(
            0.05,
            Math.min(
              0.95,
              last + pull + (Math.random() - 0.5) * VOLATILITY * 6
            )
          );

          // Slide window forward
          pts.shift();
          pts.push(next);
        });
      }

      // Schedule the next frame
      rafId = requestAnimationFrame(draw);
    };

    rafId = requestAnimationFrame(draw);

    // Cleanup = stop animation and remove resize listener
    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", resize);
    };
  }, []);
//Style in .tsx file, since only the background needs to be styled
//Canvas drawing logic can't go in css file
  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        zIndex: 0,
        pointerEvents: "none", // lets clicks pass through to  the UI below
      }}
    />
  );
}