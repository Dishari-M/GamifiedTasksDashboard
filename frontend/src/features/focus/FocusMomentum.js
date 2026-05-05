import { NavLink } from "react-router-dom";
import { Play, Timer, Trophy } from "@phosphor-icons/react";
import { formatMinutes } from "../../utils/dateTime";
import { formatFocusMultiplier } from "../rewards/xpRewards";

export const FocusQuestBadge = ({ quest }) => {
  if (!quest) return null;
  const percent = Math.min(100, Math.round((quest.focusMinutes / Math.max(1, quest.focusTargetMinutes)) * 100));
  return (
    <span className="focus-quest-badge" data-testid="focus-quest-target">
      <Timer size={15} weight="duotone" aria-hidden="true" />
      Quest focus {formatMinutes(quest.focusMinutes)} / {formatMinutes(quest.focusTargetMinutes)}
      <em>{percent}%</em>
    </span>
  );
};

export const FocusSavedQuestPanel = ({ savedQuest, savedQuestTask, onStartFocus }) => {
  if (!savedQuest || !savedQuestTask || savedQuest.state === "completed" || savedQuest.state === "skipped" || savedQuestTask.status === "Done") return null;
  const percent = Math.min(100, Math.round((savedQuest.focusMinutes / Math.max(1, savedQuest.focusTargetMinutes)) * 100));
  return (
    <div className="focus-quest-saved focus-reward-panel" data-testid="focus-quest-saved">
      <span className="quest-eyebrow">Session saved</span>
      <div>
        <strong>{savedQuestTask.title}</strong>
        <p>
          {formatMinutes(savedQuest.focusMinutes)} logged toward a {formatMinutes(savedQuest.focusTargetMinutes)} target. {percent}% complete.
          {savedQuest.hasFocusReward ? ` ${formatFocusMultiplier(savedQuest.rewardMultiplier)} focus reward is active.` : ""}
        </p>
        <div className="progress-track focus-saved-progress" aria-label="Saved session quest progress">
          <span className="progress-fill" style={{ width: `${percent}%` }} />
        </div>
      </div>
      <span className="quest-xp-chip" data-testid="focus-saved-reward"><Trophy size={15} weight="fill" aria-hidden="true" /> {savedQuest.rewardXp} XP available</span>
      <div className="focus-quest-saved-actions">
        <button className="primary-action" onClick={() => onStartFocus(savedQuestTask, savedQuest.id)} data-testid="focus-continue-quest-button"><Play size={19} weight="fill" aria-hidden="true" /> Continue Focus</button>
        <NavLink className="ghost-button" to="/quests" data-testid="focus-return-quest-button">Back to Quest Run</NavLink>
      </div>
    </div>
  );
};
