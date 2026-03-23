import SwiftUI

struct WorktreeDeletionProgressView: View {
    let state: WorktreeDeletionState

    @State private var pulse = false

    var body: some View {
        VStack(spacing: 0) {
            // Header bar — matches SessionDetailView style
            header

            // Accent gradient line
            LinearGradient(
                colors: [.red.opacity(0.6), .red.opacity(0)],
                startPoint: .leading,
                endPoint: .trailing
            )
            .frame(height: 1)

            // Dark terminal background with vertically centered content
            VStack(spacing: 20) {
                Spacer()

                // Pulsing trash icon
                Image(systemName: "trash")
                    .font(.system(size: 48))
                    .foregroundStyle(.red.opacity(0.7))
                    .scaleEffect(pulse ? 1.08 : 0.95)
                    .opacity(pulse ? 1.0 : 0.6)
                    .animation(
                        .easeInOut(duration: 1.2).repeatForever(autoreverses: true),
                        value: pulse
                    )
                    .onAppear { pulse = true }

                // Folder name
                Text(state.folderLabel)
                    .font(.title3.weight(.medium))
                    .foregroundStyle(.white.opacity(0.9))

                // Progress stepper
                VStack(alignment: .leading, spacing: 12) {
                    ForEach(WorktreeDeletionState.Step.allCases, id: \.rawValue) { step in
                        stepRow(step)
                    }
                }
                .padding(.horizontal, 40)

                Spacer()
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(red: 0.031, green: 0.043, blue: 0.063))
        }
    }

    // MARK: - Header

    private var header: some View {
        HStack {
            ProgressView()
                .controlSize(.small)

            VStack(alignment: .leading, spacing: 1) {
                Text("Deleting Worktree")
                    .font(.headline)

                Text("\(state.sessionCount) session\(state.sessionCount == 1 ? "" : "s")")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(.bar)
    }

    // MARK: - Step Row

    @ViewBuilder
    private func stepRow(_ step: WorktreeDeletionState.Step) -> some View {
        let status = state.stepStatuses[step] ?? .pending

        HStack(spacing: 10) {
            stepIcon(status)
                .frame(width: 20, height: 20)

            Text(step.rawValue)
                .font(.system(.body, design: .monospaced))
                .foregroundStyle(stepTextColor(status))

            Spacer()

            if case .failed(let message) = status {
                Text(message)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .lineLimit(2)
            }
        }
    }

    @ViewBuilder
    private func stepIcon(_ status: WorktreeDeletionState.StepStatus) -> some View {
        switch status {
        case .pending:
            Image(systemName: "circle")
                .foregroundStyle(.white.opacity(0.3))
        case .inProgress:
            ProgressView()
                .controlSize(.small)
        case .completed:
            Image(systemName: "checkmark.circle.fill")
                .foregroundStyle(.green)
        case .skipped:
            Image(systemName: "minus.circle.fill")
                .foregroundStyle(.gray)
        case .failed:
            Image(systemName: "xmark.circle.fill")
                .foregroundStyle(.red)
        }
    }

    private func stepTextColor(_ status: WorktreeDeletionState.StepStatus) -> Color {
        switch status {
        case .pending: .white.opacity(0.4)
        case .inProgress: .white
        case .completed: .green.opacity(0.8)
        case .skipped: .gray
        case .failed: .red
        }
    }
}
