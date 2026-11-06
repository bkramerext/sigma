import { useEffect, useRef } from 'react';
import './resume-authorization.css';

export type ResumeAuthorization = {
  kind: 'attempts' | 'duration';
  count: number;
  sessionNumber: number;
};

export default function ResumeAuthorizationDialog({ request, onAuthorize, onCancel }: {
  request: ResumeAuthorization | null;
  onAuthorize: () => void;
  onCancel: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (request && !element.open) element.showModal();
    else if (!request && element.open) element.close();
  }, [request]);

  return <dialog ref={dialog} className="project-settings-dialog resume-authorization-dialog"
    aria-labelledby="resume-authorization-title" aria-describedby="resume-authorization-message"
    onCancel={event => { event.preventDefault(); onCancel(); }}>
    <header className="settings-header">
      <h2 id="resume-authorization-title">Resume Session {request?.sessionNumber ?? ''}</h2>
      <div className="settings-actions">
        <button type="button" className="text-view-link resume-authorization-approve" disabled={!request} onClick={onAuthorize}>Authorize</button>
        <button type="button" className="text-view-link resume-authorization-cancel" autoFocus onClick={onCancel}>Cancel</button>
      </div>
    </header>
    <div className="settings-body" id="resume-authorization-message">
      {request?.kind === 'attempts' ? <>
        <p>Continuing this session requires {request.count} additional provider attempt{request.count === 1 ? '' : 's'} beyond its saved limit.</p>
        <p>This can consume more provider allowance. Your saved research will be preserved.</p>
      </> : request?.kind === 'duration' ? <>
        <p>The session has reached its active-time limit. Authorize up to {request.count} more minutes of research?</p>
        <p>Saved evidence and provider spending limits remain unchanged. Completion is not guaranteed.</p>
      </> : null}
    </div>
  </dialog>;
}
