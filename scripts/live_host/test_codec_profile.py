"""Offline #476 VP9 CPU encoder rollback/install and process-lifetime guard tests.

Source structure tests are intentionally narrow; Windows native PowerShell parser
and actual CodecProfile function evaluation remain separate host gates.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "scripts" / "live_host"


def source(name):
    return (LIVE / name).read_text(encoding="utf-8")


class CodecProfileSource(unittest.TestCase):
    def test_only_explicit_vp9_cpu_or_baseline_h264(self):
        helper = source("EncoderProfile.ps1")
        self.assertIn("@('VP9','H264')", helper)
        self.assertIn('"-PixelStreamingEncoderCodec=$VideoCodec"', helper)
        self.assertIn("'-PixelStreamingWebRTCMaxFps=30'", helper)
        self.assertIn("throw 'Only explicitly admitted VP9", helper)
        self.assertNotIn("AV1", helper.split("return @(")[-1])

    def test_editor_codec_is_command_line_not_browser_hint(self):
        launcher = source("Start-YacsLiveHost.ps1")
        bootstrap = source("bootstrap.py")
        self.assertIn("Get-YacsLiveEncoderArgs -VideoCodec $videoCodec", launcher)
        self.assertIn(") + $encoderArgs + @(", launcher)
        self.assertIn("'YACS_LIVE_CODEC'", launcher)
        self.assertIn("$env:YACS_LIVE_CODEC=$videoCodec", launcher)
        self.assertIn("requested_video_codec=$videoCodec", launcher)
        self.assertIn("requested_video_codec", bootstrap)
        self.assertIn('"negotiated_video_codec_verified": False', bootstrap)
        self.assertIn("'-EditorPixelStreamingRes=1280x720'", launcher)
        self.assertIn("'-ExecCmds=\"t.MaxFPS 30\"'", launcher)
        self.assertNotIn("PreferredCodec=", launcher)

    def test_verifier_never_labels_requested_codec_as_negotiated(self):
        status = source("Get-YacsLiveHostStatus.ps1")
        self.assertIn("requested_video_codec=$requestedCodec", status)
        self.assertIn("negotiated_video_codec_verified=$false", status)
        self.assertIn("$requestedMatches", status)
        self.assertIn("LIVE_VIDEO_VERIFIED", status)
        self.assertNotIn("CODEC_VP9_PROVEN", status)

    def test_vp9_trial_preserves_old_immutable_release_and_task_principal(self):
        upgrade = source("Upgrade-YacsLiveHostCodec.ps1")
        self.assertIn("[ValidateSet('VP9')]", upgrade)
        self.assertIn("VP9_IMMUTABLE_RELEASE_INSTALLED_NOT_STARTED", upgrade)
        self.assertIn("VP9_CODEC_UPGRADE_PREFLIGHT_PASS", upgrade)
        self.assertIn("Get-YacsUnrealHostState.ps1", upgrade)
        self.assertIn("Get-ScheduledTask -TaskName 'YACS Live Host'", upgrade)
        self.assertIn("Assert-YacsLiveTaskPrincipal", upgrade)
        self.assertIn("file_proofs=@($proofs)", upgrade)
        self.assertIn("Set-ScheduledTask -TaskName 'YACS Live Host' -Action", upgrade)
        self.assertLess(upgrade.index("if (-not $Apply)"), upgrade.index("Move-Item -LiteralPath $incomplete"))
        self.assertNotIn("Start-ScheduledTask", upgrade)
        self.assertNotIn("Stop-Process", upgrade)
        self.assertNotIn("Unregister-ScheduledTask", upgrade)
        self.assertNotIn("Remove-Item", upgrade)
        self.assertNotIn("git clean", upgrade)
        self.assertNotIn("git reset", upgrade)

    def test_rollback_is_explicit_and_no_automatic_restart(self):
        rollback = source("Rollback-YacsLiveHostCodec.ps1")
        self.assertIn("original_source_sha=$ExpectedOriginalHead", rollback)
        self.assertIn("H264_ORIGINAL_TASK_RESTORED_NO_START", rollback)
        self.assertIn("trial_release_preserved=$true", rollback)
        self.assertIn("Assert-YacsLiveTaskPrincipal", rollback)
        self.assertLess(rollback.index("if (-not $Apply)"), rollback.index("Copy-Item -LiteralPath $recordPath -Destination $trialBackup"))
        self.assertNotIn("Start-ScheduledTask", rollback)
        self.assertNotIn("Stop-Process", rollback)
        self.assertNotIn("Unregister-ScheduledTask", rollback)
        self.assertNotIn("Remove-Item", rollback)

    def test_fresh_install_uses_correct_powershell_quotes(self):
        installer = source("Install-YacsLiveHost.ps1")
        self.assertIn("$arguments='-NoLogo -NoProfile -File \"' + $startScript", installer)
        self.assertIn("video_codec='H264'", installer)

    def test_no_world_or_runner_mutation_in_codec_scripts(self):
        for name in (
            "Upgrade-YacsLiveHostCodec.ps1",
            "Rollback-YacsLiveHostCodec.ps1",
            "EncoderProfile.ps1",
            "Test-YacsLiveCodec.ps1",
        ):
            data = source(name).lower()
            with self.subTest(script=name):
                self.assertNotIn("save-asset", data)
                self.assertNotIn("saveall", data)
                self.assertNotIn("build.bat", data)
                self.assertNotIn("unrealbuildtool", data)
                self.assertNotIn("restart-service", data)


if __name__ == "__main__":
    unittest.main()
