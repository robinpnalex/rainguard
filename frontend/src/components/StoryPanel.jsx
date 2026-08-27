/**
 * Renders the scripted lifecycle replay from POST /demo/story.
 *
 * This is the safety net for demo day: it walks the full
 * detect -> confirm -> repair -> verify arc without depending on uploads,
 * GPS or venue wifi.
 */
export default function StoryPanel({ story, onClose, onSelectHazard }) {
  if (!story) return null
  return (
    <div className="panel story">
      <div className="detail-head">
        <h2>Demo story &mdash; hazard #{story.hazard_id}</h2>
        <button className="link" onClick={onClose}>close</button>
      </div>
      <ol className="story-steps">
        {story.steps.map((step) => (
          <li key={step.step} className={step.status.toLowerCase()}>
            <div className="story-head">
              <strong>{step.title}</strong>
              <span className="badge subtle">{step.status}</span>
            </div>
            <p>{step.detail}</p>
            <p className="hint">
              severity {step.severity}/10 &middot; {step.observation_count} observations
              &middot; {step.clean_observation_count} clean checks
            </p>
          </li>
        ))}
      </ol>
      <button className="ghost small" onClick={() => onSelectHazard(story.hazard_id)}>
        Open hazard #{story.hazard_id}
      </button>
    </div>
  )
}
