import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Camera,
  CameraOff,
  UserPlus,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Lock,
  ArrowRight,
  UserCheck,
  Building2,
  Sparkles,
} from "lucide-react";
import { api, apiErrorMessage } from "../services/api";
import { Locker } from "../types";

type CameraState = "idle" | "requesting" | "active" | "denied" | "not_found" | "error";

export function EnrollmentPage() {
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Form state
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("+91");
  const [selectedLockerId, setSelectedLockerId] = useState<string>("");
  const [customId, setCustomId] = useState("");
  const [useCustomId, setUseCustomId] = useState(false);

  // Auto-calculated customer ID & available lockers
  const [nextCustomerId, setNextCustomerId] = useState<string>("customer003");
  const [availableLockers, setAvailableLockers] = useState<Locker[]>([]);
  const [loadingInitial, setLoadingInitial] = useState(true);

  // Camera & Face capture state
  const [cameraState, setCameraState] = useState<CameraState>("idle");
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Success state
  const [enrollmentResult, setEnrollmentResult] = useState<{
    customer: {
      id: string;
      full_name: string;
      email: string;
      phone: string;
      role: string;
      status: string;
    };
    assigned_locker: {
      id: string;
      locker_number: string;
      locker_size: string;
      status: string;
    } | null;
    access_request?: {
      id: string;
      status: string;
      request_type: string;
    } | null;
    message: string;
  } | null>(null);


  const fetchNextIdAndLockers = useCallback(async () => {
    try {
      setError(null);
      const [idRes, lockersRes] = await Promise.all([
        api.get("/api/v1/admin/customers/next-id"),
        api.get("/api/v1/admin/lockers"),
      ]);
      if (idRes.data?.data?.next_customer_id) {
        setNextCustomerId(idRes.data.data.next_customer_id);
      }
      const avail = (lockersRes.data?.data || []).filter(
        (l: Locker) => l.status === "AVAILABLE"
      );
      setAvailableLockers(avail);
      if (avail.length > 0 && !selectedLockerId) {
        setSelectedLockerId(avail[0].id);
      }
    } catch (err) {
      console.error("Failed loading enrollment prerequisites", err);
    } finally {
      setLoadingInitial(false);
    }
  }, [selectedLockerId]);

  useEffect(() => {
    fetchNextIdAndLockers();
  }, [fetchNextIdAndLockers]);

  // Start Camera
  const startCamera = useCallback(async () => {
    setCameraState("requesting");
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: "user",
        },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraState("active");
    } catch (err: unknown) {
      if (err instanceof Error) {
        if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
          setCameraState("denied");
        } else if (err.name === "NotFoundError") {
          setCameraState("not_found");
        } else {
          setCameraState("error");
        }
      } else {
        setCameraState("error");
      }
    }
  }, []);

  // Stop Camera
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraState("idle");
  }, []);

  // Auto-start camera when component mounts
  useEffect(() => {
    startCamera();
    return () => {
      stopCamera();
    };
  }, [startCamera, stopCamera]);

  // Capture face photo from live video stream
  const capturePhoto = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Flip horizontally to mirror user perspective
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const dataUri = canvas.toDataURL("image/jpeg", 0.95);
    setCapturedImage(dataUri);
  };

  const retakePhoto = () => {
    setCapturedImage(null);
    setError(null);
    if (cameraState !== "active") {
      startCamera();
    }
  };

  // Submit enrollment
  const handleEnroll = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim()) {
      setError("Please enter customer's full name.");
      return;
    }
    if (!email.trim()) {
      setError("Please enter customer's email address.");
      return;
    }
    if (!phone.trim() || phone === "+91") {
      setError("Please enter customer's valid phone number.");
      return;
    }
    if (!capturedImage) {
      setError("Please capture the customer's face image first.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const payload = {
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        phone: phone.trim(),
        face_image: capturedImage,
        locker_id: selectedLockerId || null,
        custom_id: useCustomId ? customId.trim() : null,
      };

      const res = await api.post("/api/v1/admin/customers/enroll", payload);
      setEnrollmentResult(res.data.data);
      stopCamera();
    } catch (err: unknown) {
      setError(apiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleResetForNext = () => {
    setFullName("");
    setEmail("");
    setPhone("+91");
    setCapturedImage(null);
    setEnrollmentResult(null);
    setError(null);
    fetchNextIdAndLockers();
    startCamera();
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-primary flex items-center gap-2">
              <UserPlus className="text-blue-600" size={24} /> Customer Face Enrollment
            </h1>
            <span className="bg-blue-50 text-blue-700 text-xs font-semibold px-2.5 py-0.5 rounded-full border border-blue-200">
              Biometric Onboarding
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Capture new customer face biometrics, generate 128-d embeddings, and synchronize with Project NPN.
          </p>
        </div>

        {!enrollmentResult && (
          <div className="flex items-center gap-3">
            <div className="bg-surface border border-border px-3.5 py-1.5 rounded-lg shadow-sm flex items-center gap-2">
              <span className="text-xs text-slate-500 font-medium">Assigned ID:</span>
              <span className="font-mono text-sm font-bold text-primary">
                {useCustomId ? customId || "Custom" : nextCustomerId}
              </span>
              <button
                type="button"
                onClick={fetchNextIdAndLockers}
                title="Refresh next ID"
                className="text-slate-400 hover:text-primary transition-colors p-1"
              >
                <RefreshCw size={13} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Main Content */}
      {enrollmentResult ? (
        /* Celebration / Success Card */
        <div className="card max-w-2xl mx-auto p-8 rounded-2xl border border-emerald-200 bg-gradient-to-b from-emerald-50/40 via-white to-white shadow-lg space-y-6 text-center animate-in fade-in zoom-in-95 duration-300">
          <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto shadow-inner">
            <CheckCircle2 size={36} />
          </div>

          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-slate-900">Enrollment Successful!</h2>
            <p className="text-sm text-slate-600 max-w-md mx-auto">
              Customer <strong className="text-primary font-mono">{enrollmentResult.customer.id}</strong> has been registered with biometric face embeddings.
            </p>
          </div>

          {/* Details summary */}
          <div className="bg-slate-50 rounded-xl p-5 border border-slate-200/80 text-left space-y-3 text-sm">
            <div className="flex justify-between items-center py-1 border-b border-slate-200/60">
              <span className="text-slate-500">Customer ID:</span>
              <span className="font-mono font-bold text-primary text-base">{enrollmentResult.customer.id}</span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-slate-200/60">
              <span className="text-slate-500">Full Name:</span>
              <span className="font-semibold text-slate-800">{enrollmentResult.customer.full_name}</span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-slate-200/60">
              <span className="text-slate-500">Email &amp; Phone:</span>
              <span className="text-slate-700 text-xs font-mono">
                {enrollmentResult.customer.email} · {enrollmentResult.customer.phone}
              </span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-slate-200/60">
              <span className="text-slate-500">Assigned Locker:</span>
              {enrollmentResult.assigned_locker ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-blue-50 text-blue-700 rounded font-semibold text-xs border border-blue-200">
                  <Lock size={12} />
                  {enrollmentResult.assigned_locker.locker_number} ({enrollmentResult.assigned_locker.locker_size})
                </span>
              ) : (
                <span className="text-slate-400 text-xs">None (Unassigned)</span>
              )}
            </div>
            {enrollmentResult.access_request && (
              <div className="flex justify-between items-center py-1 border-b border-slate-200/60">
                <span className="text-slate-500">Access Request:</span>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-emerald-50 text-emerald-700 rounded font-semibold text-xs border border-emerald-200">
                  <ShieldCheck size={12} />
                  SUBMITTED (Ready for Face Verification)
                </span>
              </div>
            )}
            <div className="flex justify-between items-center py-1">
              <span className="text-slate-500">Biometric Sync:</span>
              <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold text-xs">
                <ShieldCheck size={14} /> Project NPN Active ({enrollmentResult.customer.id}.npy)
              </span>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex flex-wrap gap-3 justify-center pt-2">
            {enrollmentResult.access_request ? (
              <button
                onClick={() => navigate(`/requests/${enrollmentResult.access_request?.id}`)}
                className="btn-primary bg-emerald-600 hover:bg-emerald-700 text-white px-5 py-2.5 text-sm font-semibold flex items-center gap-2 shadow-md"
              >
                <ShieldCheck size={16} /> Verify Customer Face Now →
              </button>
            ) : null}
            <button
              onClick={handleResetForNext}
              className="btn-secondary px-4 py-2.5 text-sm flex items-center gap-1.5"
            >
              <UserPlus size={15} /> Enroll Another
            </button>
            <button
              onClick={() => navigate("/requests")}
              className="btn-secondary px-4 py-2.5 text-sm flex items-center gap-1.5"
            >
              View Requests Queue
            </button>
            <button
              onClick={() => navigate("/customers")}
              className="btn-secondary px-4 py-2.5 text-sm flex items-center gap-1.5"
            >
              Customers Directory <ArrowRight size={14} />
            </button>
          </div>
        </div>
      ) : (

        /* Enrollment Form & Camera Grid */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column: Live Webcam Stream & Capture */}
          <div className="lg:col-span-6 space-y-4">
            <div className="card overflow-hidden rounded-2xl border border-border shadow-sm p-4 bg-surface">
              <div className="flex items-center justify-between mb-3 px-1">
                <div className="flex items-center gap-2">
                  <Camera size={18} className="text-primary" />
                  <span className="font-bold text-sm text-primary">Live Face Capture</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  {cameraState === "active" ? (
                    <span className="inline-flex items-center gap-1.5 text-emerald-600 font-medium bg-emerald-50 px-2 py-0.5 rounded-full">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                      Camera Active
                    </span>
                  ) : (
                    <span className="text-slate-400">Camera Inactive</span>
                  )}
                </div>
              </div>

              {/* Viewfinder Container */}
              <div className="relative aspect-[4/3] bg-slate-900 rounded-xl overflow-hidden shadow-inner flex items-center justify-center border border-slate-800">
                {/* Live video */}
                <video
                  ref={videoRef}
                  playsInline
                  muted
                  className={`w-full h-full object-cover transform -scale-x-100 ${
                    capturedImage ? "hidden" : "block"
                  }`}
                />

                {/* Captured Image Preview */}
                {capturedImage && (
                  <img
                    src={capturedImage}
                    alt="Captured customer face"
                    className="w-full h-full object-cover"
                  />
                )}

                {/* Hidden canvas for image capture */}
                <canvas ref={canvasRef} className="hidden" />

                {/* Face Alignment Oval Guide overlay (when live camera is active and not captured) */}
                {cameraState === "active" && !capturedImage && (
                  <div className="absolute inset-0 pointer-events-none flex flex-col items-center justify-center">
                    <div className="w-52 h-72 rounded-[50%] border-2 border-dashed border-emerald-400/80 shadow-[0_0_20px_rgba(16,185,129,0.3)] flex items-center justify-center">
                      <div className="w-48 h-68 rounded-[50%] border border-emerald-400/30"></div>
                    </div>
                    <span className="mt-3 px-3 py-1 bg-black/60 backdrop-blur-md rounded-full text-emerald-300 text-xs font-medium border border-emerald-500/30 shadow-sm">
                      Align customer face within oval
                    </span>
                  </div>
                )}

                {/* Camera error / inactive overlays */}
                {cameraState === "denied" && (
                  <div className="absolute inset-0 bg-slate-900/90 flex flex-col items-center justify-center p-6 text-center text-white space-y-3">
                    <CameraOff size={36} className="text-red-400" />
                    <div className="text-sm font-semibold">Camera Access Denied</div>
                    <p className="text-xs text-slate-300 max-w-xs">
                      Please allow camera permission in browser settings to enroll customer face.
                    </p>
                    <button
                      type="button"
                      onClick={startCamera}
                      className="btn-secondary text-xs mt-2"
                    >
                      Retry Permission
                    </button>
                  </div>
                )}

                {cameraState === "not_found" && (
                  <div className="absolute inset-0 bg-slate-900/90 flex flex-col items-center justify-center p-6 text-center text-white space-y-3">
                    <CameraOff size={36} className="text-amber-400" />
                    <div className="text-sm font-semibold">No Camera Found</div>
                    <p className="text-xs text-slate-300 max-w-xs">
                      Please connect a USB webcam to capture face biometrics.
                    </p>
                  </div>
                )}
              </div>

              {/* Camera Actions Bar */}
              <div className="mt-4 flex items-center justify-between gap-3">
                {capturedImage ? (
                  <>
                    <div className="flex items-center gap-2 text-emerald-700 text-xs font-semibold bg-emerald-50 px-3 py-2 rounded-lg border border-emerald-200">
                      <CheckCircle2 size={16} /> Face image ready for enrollment
                    </div>
                    <button
                      type="button"
                      onClick={retakePhoto}
                      className="btn-secondary text-xs px-3.5 py-2 flex items-center gap-1.5"
                    >
                      <RefreshCw size={14} /> Retake Snapshot
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={cameraState === "active" ? stopCamera : startCamera}
                      className="btn-secondary text-xs px-3 py-2 flex items-center gap-1.5 text-slate-600"
                    >
                      {cameraState === "active" ? (
                        <>
                          <CameraOff size={14} /> Pause Camera
                        </>
                      ) : (
                        <>
                          <Camera size={14} /> Start Camera
                        </>
                      )}
                    </button>

                    <button
                      type="button"
                      disabled={cameraState !== "active"}
                      onClick={capturePhoto}
                      className="btn-primary text-xs px-5 py-2 flex items-center gap-2 shadow-sm font-semibold"
                    >
                      <Camera size={15} /> Capture Face Snapshot
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Biometric Info Hint */}
            <div className="p-4 rounded-xl bg-blue-50/70 border border-blue-200/80 flex items-start gap-3 text-xs text-blue-900">
              <Sparkles size={18} className="text-blue-600 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="font-semibold">Project NPN Biometric Recognition Integration</p>
                <p className="text-blue-800/90 leading-relaxed">
                  The face capture generates a 128-dimensional facial embedding vector saved as <strong className="font-mono">{useCustomId ? customId || nextCustomerId : nextCustomerId}.npy</strong> in both the system database and Project NPN datasets.
                </p>
              </div>
            </div>
          </div>

          {/* Right Column: Customer Details Form */}
          <div className="lg:col-span-6 space-y-4">
            <div className="card p-6 rounded-2xl border border-border shadow-sm bg-surface">
              <h2 className="text-base font-bold text-primary flex items-center gap-2 mb-4 pb-2 border-b border-border">
                <UserCheck size={18} className="text-blue-600" /> Customer Information
              </h2>

              <form onSubmit={handleEnroll} className="space-y-4">
                {/* Customer ID Display */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs font-semibold text-slate-700">Customer Identifier</label>
                    <button
                      type="button"
                      onClick={() => setUseCustomId(!useCustomId)}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      {useCustomId ? "Use Auto-Increment ID" : "Set Custom ID"}
                    </button>
                  </div>

                  {useCustomId ? (
                    <input
                      type="text"
                      value={customId}
                      onChange={(e) => setCustomId(e.target.value)}
                      placeholder="e.g. customer003"
                      className="w-full text-sm font-mono border border-border rounded-lg px-3.5 py-2 focus:ring-2 focus:ring-primary/20 focus:outline-none"
                    />
                  ) : (
                    <div className="flex items-center justify-between bg-slate-50 border border-slate-200 px-3.5 py-2.5 rounded-lg">
                      <span className="font-mono text-sm font-bold text-primary">{nextCustomerId}</span>
                      <span className="text-xs text-emerald-700 bg-emerald-100 font-semibold px-2 py-0.5 rounded-md">
                        Auto-Assigned
                      </span>
                    </div>
                  )}
                </div>

                {/* Full Name */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Full Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. Rajesh Kumar"
                    className="w-full text-sm border border-border rounded-lg px-3.5 py-2 focus:ring-2 focus:ring-primary/20 focus:outline-none"
                  />
                </div>

                {/* Email Address */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Email Address <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="e.g. rajesh.kumar@bank.com"
                    className="w-full text-sm border border-border rounded-lg px-3.5 py-2 focus:ring-2 focus:ring-primary/20 focus:outline-none"
                  />
                </div>

                {/* Phone Number */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Phone Number <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="tel"
                    required
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+919876543210"
                    className="w-full text-sm font-mono border border-border rounded-lg px-3.5 py-2 focus:ring-2 focus:ring-primary/20 focus:outline-none"
                  />
                </div>

                {/* Locker Assignment */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Assign Vault Locker (Optional)
                  </label>
                  <select
                    value={selectedLockerId}
                    onChange={(e) => setSelectedLockerId(e.target.value)}
                    className="w-full text-sm border border-border rounded-lg px-3.5 py-2 focus:ring-2 focus:ring-primary/20 focus:outline-none bg-white"
                  >
                    <option value="">Unassigned (Assign Later)</option>
                    {availableLockers.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.locker_number} — {l.locker_size} Locker ({l.status})
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-slate-500 mt-1">
                    {availableLockers.length} available locker(s) in this branch.
                  </p>
                </div>

                {/* Error Banner */}
                {error && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2 text-xs text-red-700">
                    <AlertCircle size={15} className="shrink-0 mt-0.5" />
                    <span>{error}</span>
                  </div>
                )}

                {/* Submit Action Button */}
                <div className="pt-2">
                  <button
                    type="submit"
                    disabled={submitting || !capturedImage || !fullName || !email}
                    className="w-full btn-primary py-3 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {submitting ? (
                      <>
                        <RefreshCw size={16} className="animate-spin" /> Enrolling Customer &amp; Saving Biometrics…
                      </>
                    ) : (
                      <>
                        <ShieldCheck size={16} /> Enroll Customer &amp; Save Face Data
                      </>
                    )}
                  </button>
                  {!capturedImage && (
                    <p className="text-xs text-center text-slate-400 mt-2">
                      Please take a face snapshot before submitting.
                    </p>
                  )}
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
