import { CheckCircle, Clock, Play, Timer, Trophy } from "@phosphor-icons/react";
import { formatMinutes } from "../../utils/dateTime";

const slug = (value) => String(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

const questPercent = (quest) => Math.min(100, Math.round((quest.focusMinutes / Math.max(1, quest.focusTargetMinutes)) * 100));

export const CompletionMomentumNotice = ({ completion, nextQuestTitle, summary }) => {
  if (!completion) return null;
  return (
    <div className="completion-momentum-notice" data-testid="quest-completion-notice" role="status">
      <div className="completion-reward-mark" aria-hidden="true"><CheckCircle size={22} weight="fill" /></div>
      <div className="completion-momentum-copy">
        <span className="quest-eyebrow">Quest completed</span>
        <strong>{completion.taskTitle}</strong>
        <p>
          Task marked Done. {completion.rewardXp ? `+${completion.rewardXp} XP earned. ` : ""}
          {summary?.total ? `${summary.completed}/${summary.total} quests complete.` : ""}
        </p>
        {nextQuestTitle && <p className="completion-next-step">Next up: {nextQuestTitle}</p>}
      </div>
    </div>
  );
};

export const QuestSummaryPanel = ({ summary }) => {
  const completionPercent = summary.total ? Math.round((summary.completed / summary.total) * 100) : 0;
  return (
    <aside className="quest-summary quest-reward-summary" data-testid="quest-summary">
      <div className="quest-run-meter" aria-label="Daily quest run progress">
        <span><strong>{completionPercent}%</strong>run progress</span>
        <div className="progress-track quest-run-progress"><span className="progress-fill" style={{ width: `${completionPercent}%` }} /></div>
      </div>
      <span><strong>{summary.completed}/{summary.total}</strong>complete</span>
      <span><strong>{formatMinutes(summary.focusMinutes)}</strong>focus</span>
      <span><strong>{summary.earnedXp}/{summary.availableXp}</strong>XP</span>
      <span><strong>{summary.skipped}</strong>skipped</span>
    </aside>
  );
};

export const NextQuestCard = ({
  nextQuest,
  nextQuestTask,
  summary,
  activeSessionMatchesNextQuest,
  activeSessionConflicts,
  skipReason,
  skipReasons,
  onStartFocus,
  onCompleteQuest,
  onSkipQuest,
  onSkipReasonChange,
}) => {
  const completionPercent = summary.total ? Math.round((summary.completed / summary.total) * 100) : 0;
  if (!nextQuestTask) {
    return (
      <article className="next-quest-card next-quest-complete" data-testid="next-quest-card">
        <div className="next-quest-copy">
          <span className="quest-eyebrow">Run complete</span>
          <h3 data-testid="next-quest-title">Daily run complete</h3>
          <p data-testid="next-quest-reason">Completed {summary.completed} of {summary.total}, skipped {summary.skipped}, earned {summary.earnedXp} XP, and captured {formatMinutes(summary.focusMinutes)} of focus.</p>
        </div>
      </article>
    );
  }

  return (
    <article className="next-quest-card next-quest-active-card" data-testid="next-quest-card">
      <div className="next-quest-copy">
        <div className="quest-title-line">
          <span className="quest-eyebrow" data-testid="next-quest-rank">Next quest</span>
          <span className="quest-xp-chip"><Trophy size={15} weight="fill" aria-hidden="true" /> +{nextQuest.rewardXp} XP</span>
        </div>
        <h3 data-testid="next-quest-title">{nextQuestTask.title}</h3>
        <p data-testid="next-quest-reason">{nextQuest.reason}</p>
        <div className="quest-facts" aria-label="Next quest details">
          <span data-testid="next-quest-effort"><Clock size={16} weight="duotone" aria-hidden="true" /> {formatMinutes(nextQuestTask.time)} effort</span>
          <span data-testid="next-quest-focus-progress"><Timer size={16} weight="duotone" aria-hidden="true" /> {formatMinutes(nextQuest.focusMinutes)} / {formatMinutes(nextQuest.focusTargetMinutes)} focus</span>
          <span data-testid="next-quest-xp"><Trophy size={16} weight="duotone" aria-hidden="true" /> {completionPercent}% run</span>
        </div>
        <div className="quest-progress-stack">
          <div className="progress-track quest-progress-big" aria-label={`${nextQuestTask.title} focus target progress`}>
            <span className="progress-fill" style={{ width: `${questPercent(nextQuest)}%` }} />
          </div>
          <span>{questPercent(nextQuest)}% of focus target captured</span>
        </div>
      </div>
      <div className="next-quest-actions" data-testid="next-quest-actions">
        <button className="primary-action quest-primary-action" onClick={onStartFocus} data-testid="quest-start-focus-button">
          <Play size={19} weight="fill" aria-hidden="true" /> {activeSessionMatchesNextQuest ? "Resume Focus" : activeSessionConflicts ? "Open Focus" : "Start Focus"}
        </button>
        {activeSessionConflicts && <p className="quest-focus-warning" data-testid="quest-focus-warning">A focus session is already running. Open Focus Mode to wrap it before starting this quest.</p>}
        <button className="ghost-button success-action" onClick={() => onCompleteQuest(nextQuest.id)} data-testid="quest-complete-button"><CheckCircle size={19} weight="duotone" aria-hidden="true" /> Complete quest</button>
        <div className="skip-control">
          <label htmlFor="quest-skip-reason">Skip reason</label>
          <select id="quest-skip-reason" value={skipReason} onChange={(event) => onSkipReasonChange(event.target.value)} data-testid="quest-skip-reason-select">
            {skipReasons.map((reason) => <option key={reason} value={reason}>{reason}</option>)}
          </select>
          <button className="ghost-button" onClick={() => onSkipQuest(nextQuest.id, skipReason)} data-testid="quest-skip-button">Skip</button>
        </div>
      </div>
    </article>
  );
};

export const QuestPathList = ({ questRows, onActivateQuest }) => (
  <div className="quest-path-list">
    {questRows.map(({ quest, task }) => (
      <article className={`quest-path-row quest-state-${quest.state}`} key={quest.id} data-testid={`quest-path-row-${slug(task.id)}`}>
        <span className="quest-path-rank">#{quest.rank}</span>
        <div className="quest-path-copy">
          <strong>{task.title}</strong>
          <span>{quest.reasonLabel} - {task.priority} - {formatMinutes(task.time)} - {quest.rewardXp} XP</span>
          <div className="progress-track quest-progress" aria-label={`${task.title} focus progress`}>
            <span className="progress-fill" style={{ width: `${questPercent(quest)}%` }} />
          </div>
          {quest.state === "completed" && <p className="quest-earned-copy">Earned {quest.rewardXp} XP and moved the task to Done.</p>}
          {quest.state === "skipped" && <p>Skipped: {quest.skipReason}</p>}
        </div>
        <div className="quest-path-state">
          <span className={`pill pill-${slug(quest.state)}`} data-testid={`quest-state-${slug(task.id)}`}>{quest.state}</span>
          {quest.state === "queued" && <button className="ghost-button" onClick={() => onActivateQuest(quest.id)} data-testid={`quest-activate-${slug(task.id)}`}>Choose</button>}
          {quest.state === "skipped" && <button className="ghost-button" onClick={() => onActivateQuest(quest.id)} data-testid={`quest-resume-${slug(task.id)}`}>Resume</button>}
        </div>
      </article>
    ))}
  </div>
);
