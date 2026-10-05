// Voice agent page: microphone -> upload -> transcript / answer / sources. The microphone, MediaRecorder and the API client are
// mocked: the assertions are about what the screen sends (endpoint, provider, speak flag, the audio file) and what it shows.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const postMultipart = vi.fn();

vi.mock("@/lib/i18n", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock("@/lib/useCurrentOrg", () => ({ useCurrentOrg: () => ({ org: { id: "org-1", name: "Acme", slug: "acme", my_role: "owner" }, loading: false }) }));
vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status: number;
    detail: unknown;
    constructor(status: number, detail: unknown) {
      super(String(detail));
      this.status = status;
      this.detail = detail;
    }
  }
  return { api: { postMultipart: (...a: unknown[]) => postMultipart(...a) }, ApiError };
});

import VoiceAgentPage from "./voice-agent/page";

class FakeRecorder {
  static last: FakeRecorder | null = null;
  mimeType = "audio/webm";
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  constructor() {
    FakeRecorder.last = this;
  }
  start() {}
  stop() {
    this.ondataavailable?.({ data: new Blob(["voice"], { type: "audio/webm" }) });
    this.onstop?.();
  }
}

function installMicrophone(granted = true) {
  const track = { stop: vi.fn() };
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: granted ? vi.fn().mockResolvedValue({ getTracks: () => [track] }) : vi.fn().mockRejectedValue(new Error("denied")) },
  });
  vi.stubGlobal("MediaRecorder", FakeRecorder);
  vi.stubGlobal("speechSynthesis", { speak: vi.fn() });
  vi.stubGlobal("SpeechSynthesisUtterance", class { constructor(public text: string) {} });
}

beforeEach(() => {
  postMultipart.mockReset();
  FakeRecorder.last = null;
});

describe("Voice agent page", () => {
  it("records, uploads to the organization's voice-agent endpoint and shows transcript, answer and sources", async () => {
    installMicrophone();
    postMultipart.mockResolvedValue({
      transcript: "what is the refund policy", answer_text: "30 days [1]", answer_audio_base64: null, response_id: "r1", credits_charged: 10,
      sources: [{ citation_number: 1, document_name: "policy.pdf", source_title: "Refund policy", source_url: null }],
    });
    render(<VoiceAgentPage />);

    await userEvent.click(screen.getByRole("button", { name: "voice_agent.start" }));
    await userEvent.click(await screen.findByRole("button", { name: "voice_agent.stop" }));

    await waitFor(() => expect(screen.getByText("what is the refund policy")).toBeTruthy());
    expect(screen.getByText("30 days [1]")).toBeTruthy();
    expect(screen.getByText(/Refund policy/)).toBeTruthy();

    const [path, fields, files] = postMultipart.mock.calls[0];
    expect(path).toBe("/voice/organizations/org-1/agent?stt_provider=local_whisper&speak=false");
    expect(fields).toEqual({});
    expect((files.file as File).name).toBe("question.webm");
    // no server audio -> the browser reads the answer itself, without the [1] citation marker
    expect((window.speechSynthesis.speak as ReturnType<typeof vi.fn>).mock.calls.length).toBe(1);
  });

  it("sends the chosen provider and the server-speech flag", async () => {
    installMicrophone();
    postMultipart.mockResolvedValue({ transcript: "t", answer_text: "a", answer_audio_base64: null, response_id: "r", sources: [], credits_charged: 0 });
    render(<VoiceAgentPage />);

    await userEvent.selectOptions(screen.getByRole("combobox"), "deepgram");
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: "voice_agent.start" }));
    await userEvent.click(await screen.findByRole("button", { name: "voice_agent.stop" }));

    await waitFor(() => expect(postMultipart).toHaveBeenCalled());
    expect(postMultipart.mock.calls[0][0]).toBe("/voice/organizations/org-1/agent?stt_provider=deepgram&speak=true");
  });

  it("shows a clear message when the microphone is refused and sends nothing", async () => {
    installMicrophone(false);
    render(<VoiceAgentPage />);

    await userEvent.click(screen.getByRole("button", { name: "voice_agent.start" }));

    expect((await screen.findByRole("alert")).textContent).toBe("voice_agent.error_mic");
    expect(postMultipart).not.toHaveBeenCalled();
  });

  it("surfaces the API's own error detail (e.g. insufficient credits)", async () => {
    installMicrophone();
    const { ApiError } = await import("@/lib/api");
    postMultipart.mockRejectedValue(new ApiError(402, "Insufficient AI credits"));
    render(<VoiceAgentPage />);

    await userEvent.click(screen.getByRole("button", { name: "voice_agent.start" }));
    await userEvent.click(await screen.findByRole("button", { name: "voice_agent.stop" }));

    expect((await screen.findByRole("alert")).textContent).toBe("Insufficient AI credits");
  });
});
