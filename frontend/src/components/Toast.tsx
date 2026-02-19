import { useToast } from "@/context/ToastContext";

export default function Toast() {
  const { message, visible } = useToast();

  return (
    <div
      className={`fixed bottom-8 right-8 gradient-bg text-white px-6 py-4 rounded-lg shadow-xl z-[2000] transition-transform duration-300 ${
        visible ? "translate-y-0" : "translate-y-[150%]"
      }`}
    >
      {message}
    </div>
  );
}
