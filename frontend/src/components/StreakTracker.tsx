import { useState, useEffect } from "react";
import axios from "axios";
import { FaFire } from "react-icons/fa";
import { getToken } from "../utils/auth";
import "./StreakTracker.css";

interface StreakData {
  currentStreak: number;
  bestStreak: number;
  lastVisit: string;
  visitDays: string[];
  totalVisits: number;
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

function getTodayStr() {
  return new Date().toISOString().split("T")[0];
}

function getLastNDays(n: number): string[] {
  const days: string[] = [];
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    days.push(d.toISOString().split("T")[0]);
  }
  return days;
}

function normalizeApiStreak(raw: unknown): StreakData {
  const obj = (raw && typeof raw === "object" ? raw : {}) as Partial<StreakData>;

  const currentStreak =
    typeof obj.currentStreak === "number" && Number.isFinite(obj.currentStreak) && obj.currentStreak > 0
      ? Math.floor(obj.currentStreak)
      : 1;
  const bestStreak =
    typeof obj.bestStreak === "number" && Number.isFinite(obj.bestStreak) && obj.bestStreak > 0
      ? Math.max(Math.floor(obj.bestStreak), currentStreak)
      : currentStreak;
  const lastVisit = typeof obj.lastVisit === "string" && obj.lastVisit ? obj.lastVisit : getTodayStr();
  const visitDays = Array.isArray(obj.visitDays)
    ? obj.visitDays.filter((d): d is string => typeof d === "string" && d.length > 0)
    : [lastVisit];
  const totalVisits =
    typeof obj.totalVisits === "number" && Number.isFinite(obj.totalVisits) && obj.totalVisits > 0
      ? Math.max(Math.floor(obj.totalVisits), visitDays.length)
      : Math.max(1, visitDays.length);

  return {
    currentStreak,
    bestStreak,
    lastVisit,
    visitDays: visitDays.length > 0 ? visitDays : [getTodayStr()],
    totalVisits,
  };
}

export default function StreakTracker() {
  const [streakData, setStreakData] = useState<StreakData | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setStreakData(null);
      return;
    }

    axios
      .get(`${API_BASE}/api/auth/me/streak`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      .then((res) => {
        setStreakData(normalizeApiStreak(res.data));
      })
      .catch(() => {
        setStreakData(null);
      });
  }, []);

  if (!streakData) return null;

  const visitSet = new Set(streakData.visitDays ?? []);
  const last7 = getLastNDays(7);
  const today = getTodayStr();
  const flameCount =
    streakData.currentStreak >= 30
      ? 3
      : streakData.currentStreak >= 14
        ? 2
        : streakData.currentStreak >= 3
          ? 1
          : 0;

  const flame = (
    <>
      {flameCount > 0 ? (
        Array.from({ length: flameCount }).map((_, i) => <FaFire key={i} />)
      ) : (
        <FaFire />
      )}
    </>
  );

  const message =
    streakData.currentStreak >= 30
      ? "Legendary. Keep going."
      : streakData.currentStreak >= 14
        ? "Two weeks strong."
        : streakData.currentStreak >= 7
          ? "One week streak!"
          : streakData.currentStreak >= 3
            ? "Building a habit."
            : "Great start!";

  return (
    <div className="st-card">
      <div className="st-header">
        <span className="st-label">Daily Streak</span>
        <span className="st-flame">{flame}</span>
      </div>

      <div className="st-count">{streakData.currentStreak}</div>
      <div className="st-unit">
        day{streakData.currentStreak !== 1 ? "s" : ""} in a row
      </div>
      <p className="st-message">{message}</p>

      <div className="st-dots">
        {last7.map((day) => {
          const visited = visitSet.has(day);
          const isToday = day === today;
          return (
            <div
              key={day}
              className={[
                "st-dot",
                visited ? "st-dot-on" : "",
                isToday ? "st-dot-today" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              title={day}
            />
          );
        })}
      </div>

      <div className="st-meta">Best: {streakData.bestStreak} days</div>
    </div>
  );
}
