import { basePath as BASE_PATH } from "../lib/basePath.json";

export default function ChartLogo() {
  return (
    <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`${BASE_PATH}/assets/logos/policyengine-teal.png`}
        alt=""
        style={{
          width: 80,
          opacity: 0.8,
        }}
      />
    </div>
  );
}
