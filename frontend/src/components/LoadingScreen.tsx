/*
 * LoadingScreen.tsx
 * Animated loading screen component displayed while page data is being fetched,
 * with an optional custom message.
 */
import "./LoadingScreen.css";

interface LoadingScreenProps {
  
  message?: string;
}

export default function LoadingScreen({ message = "Loading..." }: LoadingScreenProps) {
  return (

    <div className="loading-screen">
      <div className="loading-ring">
        <div className="loading-ring-track" />
        <div className="loading-ring-arc" />
        <div className="loading-bars">
          <div className="loading-bar" />
          <div className="loading-bar" />
          <div className="loading-bar" />
          <div className="loading-bar" />
          <div className="loading-bar" />
        </div>
      </div>
      <p className="loading-message">{message}</p>
    </div>

  );
}
