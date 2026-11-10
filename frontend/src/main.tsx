    <PrivacyNoticeContent/>
  </article></main>;
}

function TermsOfServicePage() {
  useEffect(() => { document.title = 'Terms of Service · SIGMA'; }, []);
  return <main className="cloud-auth-shell terms-of-service-shell" onClick={event => { if (event.target === event.currentTarget) window.location.assign('/'); }}><article className="cloud-auth-card privacy-notice-card terms-of-service-card">
    <div className="privacy-notice-heading"><h1>Terms of Service</h1><DialogDismissButton label="Close terms of service" onClick={() => { window.location.assign('/'); }}/></div>
    <TermsOfServiceContent/>
  </article></main>;
}


installRequestErrorToasts();
createRoot(document.getElementById('root')!).render(window.location.pathname === '/privacy' ? <PrivacyNoticePage/> : window.location.pathname === '/tos' ? <TermsOfServicePage/> : new URLSearchParams(window.location.search).has('session_log') ? <SessionLogPage/> : <><CloudAuthGate/><RequestErrorToasts/></>);
