/*
 * InvestorQuiz.tsx
 * Interactive quiz component that determines the user's investor personality type
 * based on their answers to a series of risk and strategy questions.
 */
import { useState, useEffect } from "react";
import {
  FaArrowRight,
  FaBalanceScale,
  FaCrosshairs,
  FaChartLine,
  FaRocket,
  FaShieldAlt,
} from "react-icons/fa";
import type { IconType } from "react-icons";
import "../networth.css";

const QUIZ_QUESTIONS = [
  {
    id: 1,
    question: "The market drops 20% overnight. What do you do?",
    options: [
      { text: "Buy more, it's on sale!", score: 4 },
      { text: "Hold and wait it out", score: 3 },
      { text: "Sell a little to sleep at night", score: 2 },
      { text: "Sell everything immediately", score: 1 },
    ],
  },
  {
    id: 2,
    question: "What's your investment time horizon?",
    options: [
      { text: "10+ years, I'm in it for the long haul", score: 4 },
      { text: "5-10 years", score: 3 },
      { text: "2-5 years", score: 2 },
      { text: "Less than 2 years", score: 1 },
    ],
  },
  {
    id: 3,
    question: "A friend tells you about a hot new stock. You:",
    options: [
      { text: "Put in a significant chunk right away", score: 4 },
      { text: "Research it first, then invest a little", score: 3 },
      { text: "Ask a few more people before deciding", score: 2 },
      { text: "Stick to your current plan", score: 1 },
    ],
  },
  {
    id: 4,
    question: "What best describes your financial goal?",
    options: [
      { text: "Maximum growth, I can handle volatility", score: 4 },
      { text: "Growth with some stability", score: 3 },
      { text: "Stability with some growth", score: 2 },
      { text: "Preserve my capital above all", score: 1 },
    ],
  },
  {
    id: 5,
    question: "How often do you check your portfolio?",
    options: [
      { text: "Multiple times a day. I love it!", score: 4 },
      { text: "Once a day or a few times a week", score: 3 },
      { text: "Once a month or so", score: 2 },
      { text: "Rarely, set it and forget it", score: 1 },
    ],
  },
];

const QUIZ_PROFILES: Array<{
  min: number;
  max: number;
  label: string;
  icon: IconType;
  description: string;
  allocation: { stocks: number; bonds: number; cash: number };
  color: string;
  borderColor: string;
  bg: string;
}> = [
  {
    min: 17,
    max: 20,
    label: "Risk Taker",
    icon: FaRocket,
    description:
      "You thrive on volatility and see every dip as an opportunity. You're built for high-growth and high-risk strategies. Think of emerging markets, small-caps, and speculative plays.",
    allocation: { stocks: 90, bonds: 5, cash: 5 },
    color: "#10b981",
    borderColor: "rgba(16, 185, 129, 0.3)",
    bg: "rgba(16, 185, 129, 0.07)",
  },
  {
    min: 13,
    max: 16,
    label: "Growth Seeker",
    icon: FaChartLine,
    description:
      "You want strong returns and can stomach moderate swings. A diversified equity portfolio with some international exposure suits you well.",
    allocation: { stocks: 75, bonds: 15, cash: 10 },
    color: "#818cf8",
    borderColor: "rgba(129, 140, 248, 0.3)",
    bg: "rgba(129, 140, 248, 0.07)",
  },
  {
    min: 9,
    max: 12,
    label: "Balanced Investor",
    icon: FaBalanceScale,
    description:
      "You want the best of both worlds, growth without too much heartache. A 60/40 portfolio or a target-date fund is right in your wheelhouse.",
    allocation: { stocks: 60, bonds: 30, cash: 10 },
    color: "#f59e0b",
    borderColor: "rgba(245, 158, 11, 0.3)",
    bg: "rgba(245, 158, 11, 0.07)",
  },
  {
    min: 5,
    max: 8,
    label: "Safe Player",
    icon: FaShieldAlt,
    description:
      "Capital preservation is your priority. You sleep better knowing your money is protected, even if it grows more slowly.",
    allocation: { stocks: 30, bonds: 50, cash: 20 },
    color: "#64748b",
    borderColor: "rgba(100, 116, 139, 0.3)",
    bg: "rgba(100, 116, 139, 0.07)",
  },
];

function AllocBar({
  label,
  pct,
  color,
}: {
  label: string;
  pct: number;
  color: string;
}) {
  return (
    <div className="quiz-alloc-row">
      <div className="quiz-alloc-label">{label}</div>
      <div className="quiz-alloc-track">
        <div
          className="quiz-alloc-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <div className="quiz-alloc-pct">{pct}%</div>
    </div>
  );
}

const DEFAULT_STATE = {
  started: false,
  answers: {} as Record<number, number>,
  submitted: false,
  profileLabel: null as string | null,
};

export default function InvestorQuiz() {
  const [started, setStarted] = useState<boolean>(DEFAULT_STATE.started);
  const [answers, setAnswers] = useState<Record<number, number>>(
    DEFAULT_STATE.answers,
  );
  const [submitted, setSubmitted] = useState<boolean>(DEFAULT_STATE.submitted);
  const [profile, setProfile] = useState<(typeof QUIZ_PROFILES)[0] | null>(
    null,
  );

  // Always start fresh for each new visit/user session.
  useEffect(() => {
    localStorage.removeItem("investorQuizState");
  }, []);

  const answer = (questionId: number, score: number) => {
    setAnswers((prev) => ({ ...prev, [questionId]: score }));
  };

  const submit = () => {
    const total = Object.values(answers).reduce((a, b) => a + b, 0);
    const found = QUIZ_PROFILES.find((p) => total >= p.min && total <= p.max);
    setProfile(found || QUIZ_PROFILES[2]);
    setSubmitted(true);
  };

  const reset = () => {
    setAnswers({});
    setSubmitted(false);
    setProfile(null);
    setStarted(false);
    localStorage.removeItem("investorQuizState");
  };

  const answered = Object.keys(answers).length;
  const progress = (answered / QUIZ_QUESTIONS.length) * 100;

  if (!started) {
    return (
      <div className="quiz-section">
        <div className="quiz-start-screen">
          <div className="quiz-start-emoji" aria-hidden="true">
            <FaCrosshairs />
          </div>
          <h2 className="quiz-start-title">Investor Personality Quiz</h2>
          <p className="quiz-start-desc">
            Find out what kind of investor you are with this short quiz
          </p>
          <button className="quiz-start-btn" onClick={() => setStarted(true)}>
            Start Quiz <FaArrowRight />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="quiz-section">
      <div className="quiz-section-header">
        <h2 className="nw-section-title">Investor Personality Quiz</h2>
        <p className="quiz-section-sub">
          Find out what kind of investor you are
        </p>
      </div>

      {submitted && profile ? (
        <div className="quiz-inner">
          <div
            className="quiz-result-card"
            style={{ borderColor: profile.borderColor, background: profile.bg }}
          >
            <div className="quiz-result-label" style={{ color: profile.color }}>
              Your Profile
            </div>
            <div className="quiz-result-name" style={{ color: profile.color }}>
              <profile.icon style={{ marginRight: "0.5rem" }} />
              {profile.label}
            </div>
            <p className="quiz-result-desc">{profile.description}</p>
            <div className="quiz-alloc-title">Suggested Allocation</div>
            <div className="quiz-alloc-bars">
              <AllocBar
                label="Stocks"
                pct={profile.allocation.stocks}
                color="#6366f1"
              />
              <AllocBar
                label="Bonds"
                pct={profile.allocation.bonds}
                color="#10b981"
              />
              <AllocBar
                label="Cash"
                pct={profile.allocation.cash}
                color="#64748b"
              />
            </div>
          </div>
          <button className="quiz-retake-btn" onClick={reset}>
            Retake Quiz
          </button>
        </div>
      ) : (
        <div className="quiz-inner">
          <div className="quiz-progress-bar-track">
            <div
              className="quiz-progress-bar-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="quiz-progress-label">
            {answered} of {QUIZ_QUESTIONS.length} answered
          </div>

          <div className="quiz-questions">
            {QUIZ_QUESTIONS.map((q) => (
              <div key={q.id} className="quiz-question-block">
                <p className="quiz-question-text">
                  <span className="quiz-q-num">{q.id}.</span> {q.question}
                </p>
                <div className="quiz-options">
                  {q.options.map((opt) => (
                    <button
                      key={opt.score}
                      className={`quiz-option-btn ${
                        answers[q.id] === opt.score ? "selected" : ""
                      }`}
                      onClick={() => answer(q.id, opt.score)}
                    >
                      {opt.text}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <button
            className="quiz-submit-btn"
            disabled={answered < QUIZ_QUESTIONS.length}
            onClick={submit}
          >
            {answered < QUIZ_QUESTIONS.length
              ? `Answer all questions (${QUIZ_QUESTIONS.length - answered} left)`
              : "See My Profile"}
            {answered >= QUIZ_QUESTIONS.length && (
              <FaArrowRight style={{ marginLeft: "0.35rem" }} />
            )}
          </button>
        </div>
      )}
    </div>
  );
}
