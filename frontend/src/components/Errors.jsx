// Shows backend rule errors: "R3 · Your price ₹9,000 is outside ..."
export default function Errors({ errors }) {
  if (!errors || errors.length === 0) return null;
  return (
    <div className="errors" role="alert">
      {errors.map((e, i) => (
        <div key={i}>
          <strong>{e.rule}</strong> · {e.message}
        </div>
      ))}
    </div>
  );
}

export function toErrors(err) {
  return err?.errors || [{ rule: "ERROR", message: String(err?.message || err) }];
}
