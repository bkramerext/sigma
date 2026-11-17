/** A saved score is something to view, not a reason to spend again. */
export function activatePaperScoreStep(
  hasSavedScore: boolean,
  showScore: () => void,
  score: () => void,
): void {
  if (hasSavedScore) showScore();
  else score();
}
