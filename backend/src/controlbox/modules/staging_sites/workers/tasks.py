from controlbox.shared.infrastructure.celery.app import celery_app


@celery_app.task(name="staging.provision", bind=True, max_retries=2)
def provision_staging_site(self, staging_id: str) -> None:
    from controlbox.modules.staging_sites.application.provision_service import run_provision_staging

    try:
        run_provision_staging(staging_id)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="staging.sync", bind=True, max_retries=1)
def sync_staging_site(self, staging_id: str, sync_type: str, direction: str) -> None:
    from controlbox.modules.staging_sites.application.provision_service import run_sync_staging

    try:
        run_sync_staging(staging_id, sync_type, direction)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=15)


@celery_app.task(name="staging.delete")
def delete_staging_site(staging_id: str) -> None:
    from controlbox.modules.staging_sites.application.provision_service import run_delete_staging

    run_delete_staging(staging_id)


@celery_app.task(name="staging.restart")
def restart_staging_site(staging_id: str) -> None:
    import asyncio
    from uuid import UUID

    from controlbox.config.settings import get_settings
    from controlbox.modules.identity.infrastructure.unit_of_work import Database
    from controlbox.modules.staging_sites.infrastructure.provisioner import StagingProvisioner

    settings = get_settings()
    database = Database(settings)
    provisioner = StagingProvisioner(settings)

    async def _restart() -> None:
        async with database.unit_of_work() as uow:
            staging = await uow.staging_sites.get_by_id(UUID(staging_id))
            if staging:
                await provisioner.restart(staging)

    asyncio.run(_restart())


def run_php_script_in_container(staging_id: str, script_name: str, args: list[str] = []) -> None:
    import json
    import shutil
    import subprocess
    from pathlib import Path
    from uuid import UUID
    import asyncio
    
    from controlbox.config.settings import get_settings
    from controlbox.modules.identity.infrastructure.unit_of_work import Database
    from controlbox.modules.staging_sites.domain.entities import StagingStatus
    
    settings = get_settings()
    db = Database(settings)
    
    async def _get_staging():
        async with db.unit_of_work() as uow:
            return await uow.staging_sites.get_by_id(UUID(staging_id))
    staging = asyncio.run(_get_staging())
    if not staging:
        return
        
    site_path = Path(staging.site_path)
    cms_dir = "wordpress" if staging.stack_type == "wordpress" else "joomla"
    target_dir = site_path / cms_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    
    migrators_dir = Path(__file__).resolve().parent.parent / "infrastructure" / "migrators"
    src_script = migrators_dir / script_name
    dest_script = target_dir / "cb_temp_helper.php"
    shutil.copy2(src_script, dest_script)
    
    try:
        compose_file = site_path / "docker-compose.yml"
        cmd = [
            "docker", "compose", "-f", str(compose_file),
            "exec", "-T", "php", "php", "cb_temp_helper.php"
        ] + args
        
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        for line in proc.stdout:
            try:
                data = json.loads(line.strip())
                percent = data.get("percent")
                status_text = data.get("status")
                if percent is not None:
                    async def _update_progress():
                        async with db.unit_of_work() as uow:
                            stg = await uow.staging_sites.get_by_id(UUID(staging_id))
                            if stg:
                                stg.settings["migration_progress"] = percent
                                stg.settings["migration_status"] = status_text
                                if percent >= 100:
                                    stg.settings.pop("migration_progress", None)
                                    stg.settings.pop("migration_status", None)
                                    stg.status = StagingStatus.RUNNING
                                await uow.staging_sites.save(stg)
                                await uow.commit()
                    asyncio.run(_update_progress())
            except Exception:
                pass
                
        proc.wait()
        
        async def _finish():
            async with db.unit_of_work() as uow:
                stg = await uow.staging_sites.get_by_id(UUID(staging_id))
                if stg:
                    stg.settings.pop("migration_progress", None)
                    stg.settings.pop("migration_status", None)
                    stg.status = StagingStatus.RUNNING
                    await uow.staging_sites.save(stg)
                    await uow.commit()
        asyncio.run(_finish())
        
    finally:
        if dest_script.exists():
            try:
                dest_script.unlink()
            except Exception:
                pass


@celery_app.task(name="staging.change_version", bind=True)
def change_staging_version(self, staging_id: str, cms_version: str, php_version: str) -> None:
    import asyncio
    from uuid import UUID
    from pathlib import Path
    import urllib.request
    import zipfile
    import shutil
    from controlbox.config.settings import get_settings
    from controlbox.modules.identity.infrastructure.unit_of_work import Database
    from controlbox.modules.staging_sites.domain.entities import StagingStatus
    from controlbox.modules.staging_sites.infrastructure.provisioner import StagingProvisioner

    settings = get_settings()
    db = Database(settings)
    provisioner = StagingProvisioner(settings)

    async def _get_staging():
        async with db.unit_of_work() as uow:
            return await uow.staging_sites.get_by_id(UUID(staging_id))
    staging = asyncio.run(_get_staging())
    if not staging:
        return

    site_path = Path(staging.site_path)

    async def _update_status(progress, status_text):
        async with db.unit_of_work() as uow:
            stg = await uow.staging_sites.get_by_id(UUID(staging_id))
            if stg:
                stg.settings["migration_progress"] = progress
                stg.settings["migration_status"] = status_text
                await uow.staging_sites.save(stg)
                await uow.commit()

    try:
        if staging.stack_type == "wordpress":
            asyncio.run(_update_status(20, "Recreating WordPress containers..."))
            db_name = staging.settings.get("db_name", "")
            db_user = staging.settings.get("db_user", "")
            db_pass = provisioner._crypto.decrypt(staging.settings.get("db_password_enc", ""))
            staging.runtime_version = php_version
            asyncio.run(provisioner.deploy_wordpress(staging, db_name, db_user, db_pass))

            asyncio.run(_update_status(60, f"Upgrading WordPress to version {cms_version}..."))
            compose_path = site_path / "docker-compose.yml"
            asyncio.run(provisioner._wp._run_wp_cli(compose_path, "wp", "core", "update", f"--version={cms_version}", "--force"))
            asyncio.run(provisioner._wp._run_wp_cli(compose_path, "wp", "core", "update-db"))
            
            asyncio.run(_update_status(100, "Done"))
            
        elif staging.stack_type == "joomla":
            asyncio.run(_update_status(20, f"Downloading Joomla {cms_version} package..."))
            download_dir = Path(settings.sites_base_path).parent / "downloads"
            download_dir.mkdir(parents=True, exist_ok=True)
            zip_path = download_dir / f"joomla-{cms_version}.zip"
            if not zip_path.exists():
                url = f"https://github.com/joomla/joomla-cms/releases/download/{cms_version}/Joomla_{cms_version}-Stable-Full_Package.zip"
                try:
                    urllib.request.urlretrieve(url, str(zip_path))
                except Exception:
                    url = f"https://github.com/joomla/joomla-cms/releases/download/{cms_version}/Joomla_{cms_version}-Stable-Update_Package.zip"
                    urllib.request.urlretrieve(url, str(zip_path))

            asyncio.run(_update_status(40, "Extracting Joomla files..."))
            dest_dir = site_path / "joomla"
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for member in zip_ref.infolist():
                    if member.filename != "configuration.php":
                        zip_ref.extract(member, dest_dir)

            asyncio.run(_update_status(60, "Recreating Joomla containers..."))
            db_name = staging.settings.get("db_name", "")
            db_user = staging.settings.get("db_user", "")
            db_pass = provisioner._crypto.decrypt(staging.settings.get("db_password_enc", ""))
            staging.runtime_version = php_version
            asyncio.run(provisioner.deploy_joomla_staging(staging, db_name, db_user, db_pass))

            asyncio.run(_update_status(80, "Running Joomla database schema updates..."))
            run_php_script_in_container(staging_id, "joomla_db_update.php")

            asyncio.run(_update_status(100, "Done"))
            
    except Exception as exc:
        async def _error(err_msg):
            async with db.unit_of_work() as uow:
                stg = await uow.staging_sites.get_by_id(UUID(staging_id))
                if stg:
                    stg.mark_error(err_msg)
                    stg.settings.pop("migration_progress", None)
                    stg.settings.pop("migration_status", None)
                    await uow.staging_sites.save(stg)
                    await uow.commit()
        asyncio.run(_error(str(exc)))


@celery_app.task(name="staging.import_blogger", bind=True)
def import_blogger_backup(self, staging_id: str, xml_file_path: str) -> None:
    try:
        import asyncio
        from uuid import UUID
        from pathlib import Path
        import shutil
        from controlbox.config.settings import get_settings
        from controlbox.modules.identity.infrastructure.unit_of_work import Database

        settings = get_settings()
        db = Database(settings)
        
        async def _get_staging():
            async with db.unit_of_work() as uow:
                return await uow.staging_sites.get_by_id(UUID(staging_id))
        staging = asyncio.run(_get_staging())
        if not staging:
            return

        site_path = Path(staging.site_path)
        cms_dir = "wordpress" if staging.stack_type == "wordpress" else "joomla"
        target_dir = site_path / cms_dir
        
        dest_xml_path = target_dir / "blogger_backup.xml"
        shutil.copy2(Path(xml_file_path), dest_xml_path)
        
        try:
            run_php_script_in_container(staging_id, "import_blogger.php", ["blogger_backup.xml"])
        finally:
            if dest_xml_path.exists():
                try:
                    dest_xml_path.unlink()
                except Exception:
                    pass
            xml_host = Path(xml_file_path)
            if xml_host.exists():
                try:
                    xml_host.unlink()
                except Exception:
                    pass
    except Exception as exc:
        db = Database(get_settings())
        async def _error(err_msg):
            async with db.unit_of_work() as uow:
                stg = await uow.staging_sites.get_by_id(UUID(staging_id))
                if stg:
                    stg.mark_error(err_msg)
                    stg.settings.pop("migration_progress", None)
                    stg.settings.pop("migration_status", None)
                    await uow.staging_sites.save(stg)
                    await uow.commit()
        asyncio.run(_error(str(exc)))


@celery_app.task(name="staging.migrate_joomla_to_wp", bind=True)
def migrate_joomla_to_wp(self, staging_id: str) -> None:
    import asyncio
    import re
    import time
    import zipfile
    import urllib.request
    from uuid import UUID
    from pathlib import Path
    import shutil
    from controlbox.config.settings import get_settings
    from controlbox.modules.identity.infrastructure.unit_of_work import Database
    from controlbox.modules.staging_sites.domain.entities import StagingStatus, StagingStackType
    from controlbox.modules.staging_sites.infrastructure.provisioner import StagingProvisioner

    settings = get_settings()
    db = Database(settings)
    provisioner = StagingProvisioner(settings)

    async def _get_staging():
        async with db.unit_of_work() as uow:
            return await uow.staging_sites.get_by_id(UUID(staging_id))
    staging = asyncio.run(_get_staging())
    if not staging:
        return

    site_path = Path(staging.site_path)

    async def _update_status(progress, status_text):
        async with db.unit_of_work() as uow:
            stg = await uow.staging_sites.get_by_id(UUID(staging_id))
            if stg:
                stg.settings["migration_progress"] = progress
                stg.settings["migration_status"] = status_text
                await uow.staging_sites.save(stg)
                await uow.commit()

    try:
        asyncio.run(_update_status(10, "Reading Joomla configuration prefix..."))
        config_file = site_path / "joomla" / "configuration.php"
        prefix = "jos_"
        if config_file.exists():
            content = config_file.read_text(encoding="utf-8", errors="replace")
            match = re.search(r"public\s+\$dbprefix\s*=\s*['\"](.*?)['\"]", content)
            if match:
                prefix = match.group(1)

        asyncio.run(_update_status(20, "Moving Joomla files..."))
        joomla_old = site_path / "joomla_old"
        if joomla_old.exists():
            shutil.rmtree(joomla_old)
        if (site_path / "joomla").exists():
            shutil.move(str(site_path / "joomla"), str(joomla_old))

        asyncio.run(_update_status(30, "Downloading WordPress 6.x..."))
        wp_dir = site_path / "wordpress"
        if wp_dir.exists():
            shutil.rmtree(wp_dir)
        wp_dir.mkdir(parents=True, exist_ok=True)
        
        download_dir = Path(settings.sites_base_path).parent / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        wp_zip = download_dir / "wordpress-6.5.5.zip"
        if not wp_zip.exists():
            urllib.request.urlretrieve("https://wordpress.org/wordpress-6.5.5.zip", str(wp_zip))
            
        asyncio.run(_update_status(40, "Extracting WordPress files..."))
        temp_extract = site_path / "wp_temp"
        if temp_extract.exists():
            shutil.rmtree(temp_extract)
        with zipfile.ZipFile(wp_zip, 'r') as zip_ref:
            zip_ref.extractall(temp_extract)
        shutil.copytree(temp_extract / "wordpress", wp_dir, dirs_exist_ok=True)
        shutil.rmtree(temp_extract)

        asyncio.run(_update_status(50, "Stopping Joomla staging containers..."))
        compose_path = site_path / "docker-compose.yml"
        if compose_path.exists():
            try:
                asyncio.run(provisioner._exec("docker", "compose", "-f", str(compose_path), "down", "-v", "--remove-orphans", cwd=site_path))
            except Exception:
                pass

        asyncio.run(_update_status(60, "Configuring WordPress containers..."))
        db_name = staging.settings.get("db_name", "")
        db_user = staging.settings.get("db_user", "")
        db_pass = provisioner._crypto.decrypt(staging.settings.get("db_password_enc", ""))
        
        staging.stack_type = StagingStackType.WORDPRESS
        short = staging.id.hex[:12]
        staging.container_name = f"cb-stg-wp-{short}"
        staging.nginx_container_name = f"cb-stg-nginx-{short}"
        staging.php_container_name = f"cb-stg-php-{short}"
        
        asyncio.run(provisioner.deploy_wordpress(staging, db_name, db_user, db_pass))

        asyncio.run(_update_status(70, "Installing WordPress core..."))
        compose_path = site_path / "docker-compose.yml"
        time.sleep(5)
        try:
            asyncio.run(provisioner._wp._run_wp_cli(
                compose_path,
                "wp", "core", "install",
                f"--url=https://{staging.domain}",
                f"--title={staging.name}",
                "--admin_user=admin",
                "--admin_password=admin_password_strong",
                "--admin_email=admin@example.com",
                "--skip-email"
            ))
        except Exception:
            pass

        asyncio.run(_update_status(80, "Migrating data from Joomla to WordPress..."))
        run_php_script_in_container(str(staging.id), "joomla_to_wp.php", [prefix])

        asyncio.run(_update_status(95, "Cleaning up Joomla backup files..."))
        if joomla_old.exists():
            shutil.rmtree(joomla_old)

        async def _save_stack():
            async with db.unit_of_work() as uow:
                stg = await uow.staging_sites.get_by_id(UUID(staging_id))
                if stg:
                    stg.stack_type = StagingStackType.WORDPRESS
                    stg.container_name = f"cb-stg-wp-{short}"
                    stg.nginx_container_name = f"cb-stg-nginx-{short}"
                    stg.php_container_name = f"cb-stg-php-{short}"
                    stg.settings.pop("migration_progress", None)
                    stg.settings.pop("migration_status", None)
                    stg.status = StagingStatus.RUNNING
                    await uow.staging_sites.save(stg)
                    await uow.commit()
        asyncio.run(_save_stack())

    except Exception as exc:
        async def _error(err_msg):
            async with db.unit_of_work() as uow:
                stg = await uow.staging_sites.get_by_id(UUID(staging_id))
                if stg:
                    stg.mark_error(err_msg)
                    stg.settings.pop("migration_progress", None)
                    stg.settings.pop("migration_status", None)
                    await uow.staging_sites.save(stg)
                    await uow.commit()
        asyncio.run(_error(str(exc)))

