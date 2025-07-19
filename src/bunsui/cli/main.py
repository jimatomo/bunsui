"""
Main CLI entry point for Bunsui.

This module provides the main command-line interface for Bunsui.
"""

import sys
import click
from typing import Optional

from .. import __version__

# Import command modules
from .commands import pipeline, session, logs, config, init
from .interactive import start_interactive


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--profile', '-p', help='AWS profile to use')
@click.option('--region', '-r', help='AWS region')
@click.version_option(version=__version__, prog_name='bunsui')
@click.pass_context
def cli(ctx: click.Context, verbose: bool, config: Optional[str], profile: Optional[str], region: Optional[str]):
    """
    Bunsui - OSS TUI Data Pipeline Management Tool for AWS.
    
    A powerful, extensible data pipeline management tool with AWS integration.
    """
    # Ensure that ctx.obj exists and is a dict
    ctx.ensure_object(dict)
    
    # Store global options in context
    ctx.obj['verbose'] = verbose
    ctx.obj['config'] = config
    ctx.obj['profile'] = profile
    ctx.obj['region'] = region
    
    if verbose:
        click.echo(f"Bunsui v{__version__}")
        if config:
            click.echo(f"Using config: {config}")
        if profile:
            click.echo(f"Using AWS profile: {profile}")
        if region:
            click.echo(f"Using AWS region: {region}")


@cli.command()
@click.pass_context
def version(ctx: click.Context):
    """Show version information."""
    click.echo(f"Bunsui version {__version__}")
    
    if ctx.obj.get('verbose'):
        import boto3
        import pydantic
        import rich
        
        click.echo(f"Python: {sys.version}")
        click.echo(f"boto3: {boto3.__version__}")
        click.echo(f"pydantic: {pydantic.VERSION}")
        try:
            import importlib.metadata
            rich_version = importlib.metadata.version("rich")
            click.echo(f"rich: {rich_version}")
        except (AttributeError, ImportError):
            click.echo("rich: version not available")


# Add command groups
cli.add_command(pipeline.pipeline)
cli.add_command(session.session)
cli.add_command(logs.logs)
cli.add_command(config.config)
cli.add_command(init.init)


@cli.command()
@click.pass_context
def tui(ctx: click.Context):
    """Launch the TUI interface."""
    click.echo("Launching Bunsui TUI...")
    click.echo("TUI functionality will be implemented soon.")


@cli.command()
@click.pass_context
def interactive(ctx: click.Context):
    """Launch interactive mode."""
    start_interactive(ctx)


@cli.command()
@click.option('--check-aws', is_flag=True, help='Check AWS connectivity')
@click.option('--check-config', is_flag=True, help='Check configuration')
@click.pass_context
def doctor(ctx: click.Context, check_aws: bool, check_config: bool):
    """Run diagnostics and health checks."""
    click.echo("Running Bunsui diagnostics...")
    
    if check_aws:
        click.echo("Checking AWS connectivity...")
        # TODO: Implement AWS connectivity check
        click.echo("✓ AWS connectivity check will be implemented soon")
    
    if check_config:
        click.echo("Checking configuration...")
        # TODO: Implement configuration check
        click.echo("✓ Configuration check will be implemented soon")
    
    if not check_aws and not check_config:
        click.echo("Running all checks...")
        click.echo("✓ All checks will be implemented soon")


def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\nOperation cancelled by user.", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main() 